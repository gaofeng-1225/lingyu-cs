import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { RtcConfig, SceneInfo } from '../api/client';
import { AGENT_STAGE } from '../lib/messageParser';

export interface ChatMsg {
  id: string;
  role: 'user' | 'ai';
  text: string;
  final: boolean;
}

export type CallStatus = 'idle' | 'connecting' | 'ready' | 'error';

interface RoomState {
  scene: SceneInfo | null;
  rtc: RtcConfig | null;
  sessionId: string;
  status: CallStatus;
  errorMsg: string;
  aiStage: AGENT_STAGE;
  aiReady: boolean;
  messages: ChatMsg[];
  muted: boolean;
  autoplayFail: boolean;
  remoteAudioLevel: number;
  networkQuality: number;
}

const initialState: RoomState = {
  scene: null,
  rtc: null,
  sessionId: '',
  status: 'idle',
  errorMsg: '',
  aiStage: AGENT_STAGE.UNKNOWN,
  aiReady: false,
  messages: [],
  muted: false,
  autoplayFail: false,
  remoteAudioLevel: 0,
  networkQuality: 0,
};

let msgSeq = 0;

const roomSlice = createSlice({
  name: 'room',
  initialState,
  reducers: {
    setSession(state, action: PayloadAction<{ scene: SceneInfo; rtc: RtcConfig; sessionId: string }>) {
      state.scene = action.payload.scene;
      state.rtc = action.payload.rtc;
      state.sessionId = action.payload.sessionId;
      state.messages = [];
      state.status = 'idle';
      state.aiStage = AGENT_STAGE.UNKNOWN;
      state.aiReady = false;
    },
    setStatus(state, action: PayloadAction<{ status: CallStatus; errorMsg?: string }>) {
      state.status = action.payload.status;
      if (action.payload.errorMsg !== undefined) {
        state.errorMsg = action.payload.errorMsg;
      }
    },
    setAiStage(state, action: PayloadAction<AGENT_STAGE>) {
      state.aiStage = action.payload;
      if (action.payload !== AGENT_STAGE.UNKNOWN) {
        state.aiReady = true;
      }
    },
    /** 字幕：definite=false 为流式中间结果，definite=true 落定 */
    upsertSubtitle(
      state,
      action: PayloadAction<{ text: string; definite: boolean; userId: string; paragraph: boolean }>
    ) {
      const { text, definite, userId, paragraph } = action.payload;
      const role: 'user' | 'ai' = userId === state.scene?.botName ? 'ai' : 'user';
      const last = state.messages[state.messages.length - 1];

      if (definite) {
        // 落定：若上一条是同角色中间结果，替换之；否则新开一条
        if (last && last.role === role && !last.final) {
          last.text = text;
          last.final = true;
        } else {
          state.messages.push({ id: `m${++msgSeq}`, role, text, final: true });
        }
        if (paragraph) {
          state.messages.push({ id: `m${++msgSeq}`, role, text: '', final: false });
        }
      } else {
        if (last && last.role === role && !last.final) {
          last.text = text;
        } else {
          state.messages.push({ id: `m${++msgSeq}`, role, text, final: false });
        }
      }
    },
    clearMessages(state) {
      state.messages = [];
    },
    toggleMute(state) {
      state.muted = !state.muted;
    },
    setAutoplayFail(state, action: PayloadAction<boolean>) {
      state.autoplayFail = action.payload;
    },
    setRemoteAudioLevel(state, action: PayloadAction<number>) {
      state.remoteAudioLevel = action.payload;
    },
    setNetworkQuality(state, action: PayloadAction<number>) {
      state.networkQuality = action.payload;
    },
    reset(state) {
      Object.assign(state, initialState);
    },
  },
});

export const {
  setSession,
  setStatus,
  setAiStage,
  upsertSubtitle,
  clearMessages,
  toggleMute,
  setAutoplayFail,
  setRemoteAudioLevel,
  setNetworkQuality,
  reset,
} = roomSlice.actions;

export default roomSlice.reducer;
