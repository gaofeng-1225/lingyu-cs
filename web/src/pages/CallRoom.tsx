import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { api } from '../api/client';
import rtcClient, { InterruptPriority } from '../lib/rtcClient';
import { parseBinaryMessage, AGENT_STAGE } from '../lib/messageParser';
import {
  setSession,
  setStatus,
  setAiStage,
  upsertSubtitle,
  toggleMute,
  setAutoplayFail,
  setRemoteAudioLevel,
  setNetworkQuality,
  reset,
} from '../store/roomSlice';
import { RootState } from '../store';
import { loadSession } from './Home';
import WaveAvatar from '../components/WaveAvatar';
import MessageList from '../components/MessageList';
import ControlBar from '../components/ControlBar';

const STAGE_TEXT: Record<number, string> = {
  [AGENT_STAGE.LISTENING]: '正在聆听…',
  [AGENT_STAGE.THINKING]: 'AI 思考中…',
  [AGENT_STAGE.SPEAKING]: 'AI 正在说话',
  [AGENT_STAGE.INTERRUPTED]: '已打断',
  [AGENT_STAGE.FINISHED]: '请开始说话',
};

export default function CallRoom() {
  const { sceneId } = useParams<{ sceneId: string }>();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const room = useSelector((state: RootState) => state.room);
  const [joining, setJoining] = useState(false);
  const [interruptError, setInterruptError] = useState('');
  const joinedRef = useRef(false);
  const stopRef = useRef<() => Promise<void>>(async () => undefined);

  // 初始化：恢复会话并写入 store
  useEffect(() => {
    const session = loadSession();
    const entry = session?.scenes.find((s) => s.scene.id === sceneId);
    if (!session || !entry) {
      navigate('/', { replace: true });
      return;
    }
    dispatch(setSession({ scene: entry.scene, rtc: entry.rtc, sessionId: session.SessionID }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneId]);

  const stopCall = useCallback(async () => {
    const { sessionId, scene, status } = room;
    if (sessionId && scene && status !== 'idle') {
      try {
        await api.stopVoiceChat({ SessionID: sessionId, SceneID: scene.id });
      } catch {
        /* ignore */
      }
    }
    await rtcClient.leaveRoom();
    dispatch(reset());
    joinedRef.current = false;
  }, [room, dispatch]);
  stopRef.current = stopCall;

  // 页面关闭时兜底停止
  useEffect(() => {
    const onUnload = () => {
      const session = loadSession();
      const entry = session?.scenes.find((s) => s.scene.id === sceneId);
      if (session && entry && joinedRef.current && navigator.sendBeacon) {
        const body = new URLSearchParams({
          SessionID: session.SessionID,
          SceneID: entry.scene.id,
        });
        navigator.sendBeacon('/proxy?Action=StopVoiceChat', body);
      }
    };
    window.addEventListener('beforeunload', onUnload);
    return () => {
      window.removeEventListener('beforeunload', onUnload);
      // 仅在真正加入过房间时才执行停止/重置，避免初始挂载的清理竞态
      if (joinedRef.current || rtcClient.engine) {
        void stopRef.current();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneId]);

  const startCall = async () => {
    if (!room.rtc || !room.scene || joining) return;
    setJoining(true);
    dispatch(setStatus({ status: 'connecting' }));

    try {
      const supported = await rtcClient.isSupported();
      if (!supported) throw new Error('当前浏览器不支持 RTC，请使用最新版 Chrome / Edge');

      const audioGranted = await rtcClient.checkAudioPermission();
      if (!audioGranted) throw new Error('未获得麦克风权限，请在浏览器地址栏允许后重试');

      rtcClient.setConfig(room.rtc, room.scene.botName);
      await rtcClient.createEngine(room.rtc.AppId);
      rtcClient.setListeners({
        onRoomBinaryMessageReceived: ({ message }) => {
          const parsed = parseBinaryMessage(message);
          if (!parsed) return;
          if (parsed.type === 'subv' && parsed.data) {
            dispatch(
              upsertSubtitle({
                text: parsed.data.text,
                definite: parsed.data.definite,
                userId: parsed.data.userId,
                paragraph: parsed.data.paragraph,
              })
            );
          } else if (parsed.type === 'conv' && parsed.stageCode !== undefined) {
            dispatch(setAiStage(parsed.stageCode));
          }
        },
        onAutoPlayFail: () => dispatch(setAutoplayFail(true)),
        onRemoteAudioLevel: (level) => dispatch(setRemoteAudioLevel(level)),
        onNetworkQuality: (quality) => dispatch(setNetworkQuality(quality)),
        onError: (e) => {
          console.error('RTC error:', e.errorCode);
          dispatch(setStatus({ status: 'error', errorMsg: `RTC 错误码 ${e.errorCode}` }));
        },
      });

      await rtcClient.joinRoom();
      await rtcClient.startMic();
      const result = await api.startVoiceChat({ SessionID: room.sessionId, SceneID: room.scene.id });
      const error = result.ResponseMetadata.Error;
      if (error) {
        throw new Error(error.Message || error.Code || '启动语音对话失败');
      }
      joinedRef.current = true;
      dispatch(setStatus({ status: 'ready' }));
    } catch (error) {
      const message = (error as Error).message || String(error);
      if (message.includes('请先调用 getScenes')) {
        await rtcClient.leaveRoom();
        joinedRef.current = false;
        navigate('/', { replace: true });
        return;
      }
      dispatch(setStatus({ status: 'error', errorMsg: message }));
      await rtcClient.leaveRoom();
    } finally {
      setJoining(false);
    }
  };

  const onMute = async () => {
    dispatch(toggleMute());
    if (!room.muted) {
      await rtcClient.stopMic();
    } else {
      await rtcClient.startMic();
    }
  };

  const onInterrupt = async () => {
    try {
      await rtcClient.interrupt(InterruptPriority.HIGH);
      setInterruptError('');
    } catch (error) {
      console.error('RTC interrupt error:', error);
      setInterruptError('打断指令未送达，AI 助手尚未接入房间，请结束后重新发起通话。');
    }
  };

  const onEnd = async () => {
    await stopCall();
    navigate('/', { replace: true });
  };

  const stageText = STAGE_TEXT[room.aiStage] ?? (room.status === 'ready' ? '请开始说话' : '');

  return (
    <div className="callroom">
      <header className="callroom-header">
        <button className="back-btn" onClick={() => void onEnd()}>
          ← 返回
        </button>
        <div className="callroom-title">
          <strong>{room.scene?.name ?? '语音对话'}</strong>
          <span className={`status-dot status-${room.status}`} />
          <span className="status-text">
            {room.status === 'idle' && '未连接'}
            {room.status === 'connecting' && '连接中…'}
            {room.status === 'ready' && (stageText || '通话中')}
            {room.status === 'error' && '连接异常'}
          </span>
        </div>
        <span className="net-badge">网络 {room.networkQuality || '-'}</span>
      </header>

      <main className="callroom-main">
        <WaveAvatar
          name={room.scene?.name ?? 'AI 助手'}
          talking={room.aiStage === AGENT_STAGE.SPEAKING}
          thinking={room.aiStage === AGENT_STAGE.THINKING}
          audioLevel={room.remoteAudioLevel}
        />
        <MessageList messages={room.messages} botName={room.scene?.botName ?? ''} />
      </main>

      {room.status === 'error' && (
        <div className="call-error">
          <p>{room.errorMsg || '连接失败'}</p>
          <button onClick={startCall} disabled={joining}>
            重试
          </button>
        </div>
      )}

      {interruptError && (
        <div className="call-error">
          <p>{interruptError}</p>
        </div>
      )}

      {room.autoplayFail && (
        <button
          className="autoplay-banner"
          onClick={() => {
            rtcClient.resumeAutoplay();
            dispatch(setAutoplayFail(false));
          }}
        >
          🔊 浏览器拦截了声音播放，点击此处恢复
        </button>
      )}

      <ControlBar
        status={room.status}
        joining={joining}
        muted={room.muted}
        canInterrupt={room.status === 'ready'}
        onStart={startCall}
        onMute={onMute}
        onInterrupt={onInterrupt}
        onEnd={onEnd}
      />
    </div>
  );
}
