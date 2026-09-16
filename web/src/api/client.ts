/**
 * 服务端接口客户端（业务网关）
 */

const BASE = (import.meta.env.VITE_AIGC_PROXY_HOST || '').replace(/\/$/, '');

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      detail = data?.detail || data?.ResponseMetadata?.Error?.Message || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export interface RtcInfo {
  AppId: string;
  BusinessId?: string | null;
  RoomId: string;
  UserId: string;
  Token: string;
}

export interface SceneInfo {
  id: string;
  name: string;
  icon: string;
  questions: string[];
  botName: string;
  isInterruptMode: boolean;
  isAvatarScene: boolean | null;
  avatarBgUrl: string | null;
  isVision: boolean;
  isScreenMode: boolean;
}

export interface GetScenesResult {
  ResponseMetadata: { Action: string };
  Result: {
    SessionID: string;
    scenes: { scene: SceneInfo; rtc: RtcInfo }[];
  };
}

export interface VoiceChatResult {
  ResponseMetadata: { Action: string; Error?: { Code?: string; Message?: string } };
  Result?: unknown;
}

export const api = {
  getScenes: () => request<GetScenesResult>('/getScenes', {}),
  startVoiceChat: (payload: { SessionID: string; SceneID: string }) =>
    request<VoiceChatResult>('/proxy?Action=StartVoiceChat', payload),
  stopVoiceChat: (payload: { SessionID: string; SceneID: string }) =>
    request<VoiceChatResult>('/proxy?Action=StopVoiceChat', payload),
};
