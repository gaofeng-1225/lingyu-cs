/**
 * RTC 二进制消息解析（字幕 / 状态）
 * - subv: 字幕消息 {data: [{text, definite, userId, paragraph, roundId, sequence}]}
 * - conv: 对话状态简报 {Stage: {Code, Description}}
 * 解析结果通过回调交给 store 更新 UI。
 */
import { tlv2String } from './tlv';

export enum MESSAGE_TYPE {
  BRIEF = 'conv',
  SUBTITLE = 'subv',
  FUNCTION_CALL = 'tool',
}

/** 云端 Agent 状态码 */
export enum AGENT_STAGE {
  UNKNOWN = 0,
  LISTENING = 1,
  THINKING = 2,
  SPEAKING = 3,
  INTERRUPTED = 4,
  FINISHED = 5,
}

export interface SubtitleData {
  text: string;
  definite: boolean;
  userId: string;
  paragraph: boolean;
  roundId?: number;
  sequence?: number;
}

export interface ParsedMessage {
  type: MESSAGE_TYPE;
  data?: SubtitleData;
  stageCode?: number;
  stageDescription?: string;
  raw?: unknown;
}

export function parseBinaryMessage(buffer: ArrayBuffer): ParsedMessage | null {
  try {
    const { type, value } = tlv2String(buffer);
    const parsed = JSON.parse(value) as {
      data?: SubtitleData[];
      Stage?: { Code?: number; Description?: string };
      [key: string]: unknown;
    };

    switch (type) {
      case MESSAGE_TYPE.SUBTITLE: {
        const item = parsed.data?.[0];
        if (!item) return null;
        return { type: MESSAGE_TYPE.SUBTITLE, data: item };
      }
      case MESSAGE_TYPE.BRIEF: {
        return {
          type: MESSAGE_TYPE.BRIEF,
          stageCode: Number(parsed.Stage?.Code ?? AGENT_STAGE.UNKNOWN),
          stageDescription: parsed.Stage?.Description ?? '',
          raw: parsed,
        };
      }
      default:
        return null;
    }
  } catch {
    return null;
  }
}
