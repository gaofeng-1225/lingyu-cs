/**
 * RTC 客户端封装（火山引擎 Web SDK）
 * 职责：创建引擎、加入房间、采集/推流、打断指令、事件回调分发
 */
import VERTC, {
  IRTCEngine,
  MediaType,
  RoomProfileType,
  AutoPlayFailedEvent,
} from '@volcengine/rtc';
import { string2tlv } from './tlv';

export interface RtcConfig {
  AppId: string;
  BusinessId?: string | null;
  RoomId: string;
  UserId: string;
  Token: string;
}

export interface RtcListeners {
  onError?: (e: { errorCode: number }) => void;
  onUserJoin?: (e: { userId: string }) => void;
  onUserLeave?: (e: { userId: string }) => void;
  onUserPublishStream?: (e: { userId: string; mediaType: MediaType }) => void;
  onRoomBinaryMessageReceived?: (e: { userId: string; message: ArrayBuffer }) => void;
  onAutoPlayFail?: (e: AutoPlayFailedEvent) => void;
  onRemoteAudioLevel?: (level: number) => void;
  onNetworkQuality?: (quality: number) => void;
}

/** 打断优先级（与云端协议一致） */
export enum InterruptPriority {
  NONE = 0,
  HIGH = 1,
  MEDIUM = 2,
  LOW = 3,
}

class RtcClient {
  engine: IRTCEngine | null = null;
  config: RtcConfig | null = null;
  botName = '';
  private listeners: RtcListeners = {};

  /** 浏览器是否支持 RTC */
  async isSupported(): Promise<boolean> {
    return VERTC.isSupported();
  }

  /** 申请麦克风权限 */
  async checkAudioPermission(): Promise<boolean> {
    const result = await VERTC.enableDevices({ video: false, audio: true });
    return result.audio;
  }

  /** 创建引擎并注册 AI 降噪扩展（失败可忽略） */
  async createEngine(appId: string): Promise<void> {
    this.engine = VERTC.createEngine(appId);
    try {
      const { default: RTCAIAnsExtension } = await import('@volcengine/rtc/extension-ainr');
      const ext = new RTCAIAnsExtension();
      await this.engine.registerExtension(ext);
      ext.enable();
    } catch (error) {
      console.warn('AI 降噪扩展加载失败（可忽略）:', (error as Error).message);
    }
  }

  setConfig(config: RtcConfig, botName: string): void {
    this.config = config;
    this.botName = botName;
  }

  setListeners(listeners: RtcListeners): void {
    this.listeners = listeners;
    if (!this.engine) return;
    this.engine.on(VERTC.events.onError, (e: { errorCode: number }) =>
      this.listeners.onError?.(e)
    );
    this.engine.on(VERTC.events.onUserJoined, (e: { userId: string }) =>
      this.listeners.onUserJoin?.(e)
    );
    this.engine.on(VERTC.events.onUserLeave, (e: { userId: string }) =>
      this.listeners.onUserLeave?.(e)
    );
    this.engine.on(VERTC.events.onUserPublishStream, (e: { userId: string; mediaType: MediaType }) =>
      this.listeners.onUserPublishStream?.(e)
    );
    this.engine.on(
      VERTC.events.onRoomBinaryMessageReceived,
      (e: { userId: string; message: ArrayBuffer }) =>
        this.listeners.onRoomBinaryMessageReceived?.(e)
    );
    this.engine.on(VERTC.events.onAutoplayFailed, (e: AutoPlayFailedEvent) =>
      this.listeners.onAutoPlayFail?.(e)
    );
    this.engine.on(
      VERTC.events.onRemoteAudioPropertiesReport,
      (infos: { audioPropertiesList: { audioLevel: number }[] }) => {
        const max = Math.max(0, ...infos.audioPropertiesList.map((i) => i.audioLevel));
        this.listeners.onRemoteAudioLevel?.(max);
      }
    );
    this.engine.on(
      VERTC.events.onNetworkQuality,
      (_up: unknown, down: { quality: number }) =>
        this.listeners.onNetworkQuality?.(down.quality)
    );
  }

  /** 加入房间（自动推流 + 自动订阅远端音频） */
  async joinRoom(): Promise<void> {
    if (!this.engine || !this.config) throw new Error('engine/config 未初始化');
    const { Token, RoomId, UserId, BusinessId } = this.config;
    if (BusinessId) {
      this.engine.setBusinessId(BusinessId);
    }
    await this.engine.joinRoom(
      Token,
      RoomId,
      {
        userId: UserId,
        extraInfo: JSON.stringify({
          call_scene: 'RTC-AIGC',
          user_name: UserId,
          user_id: UserId,
        }),
      },
      {
        isAutoPublish: true,
        isAutoSubscribeAudio: true,
        roomProfileType: RoomProfileType.chat,
      }
    );
  }

  /** 开启麦克风采集并发布音频 */
  async startMic(): Promise<void> {
    if (!this.engine) return;
    await this.engine.publishStream(MediaType.AUDIO);
    await this.engine.startAudioCapture();
  }

  /** 停止麦克风采集与发布 */
  async stopMic(): Promise<void> {
    if (!this.engine) return;
    await this.engine.stopAudioCapture();
    await this.engine.unpublishStream(MediaType.AUDIO);
  }

  /** 发送打断指令（走 RTC 数据通道，毫秒级生效） */
  async interrupt(priority: InterruptPriority = InterruptPriority.HIGH): Promise<void> {
    if (!this.engine || !this.botName) throw new Error('RTC 未连接，无法发送打断指令');
    await this.engine.sendUserBinaryMessage(
      this.botName,
      string2tlv(
        JSON.stringify({
          Command: 'interrupt',
          InterruptMode: priority,
          Message: '',
        }),
        'ctrl'
      )
    );
  }

  /** 尝试恢复自动播放（浏览器限制时用户点击后调用） */
  resumeAutoplay(): void {
    try {
      (this.engine as unknown as { resumeAutoplay?: () => void }).resumeAutoplay?.();
    } catch {
      /* ignore */
    }
  }

  /** 离开房间并销毁引擎 */
  async leaveRoom(): Promise<void> {
    if (!this.engine) return;
    try {
      await this.engine.leaveRoom();
    } catch {
      /* ignore */
    }
    VERTC.destroyEngine(this.engine);
    this.engine = null;
  }
}

export default new RtcClient();
