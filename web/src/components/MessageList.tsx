import { ChatMsg } from '../store/roomSlice';

interface MessageListProps {
  messages: ChatMsg[];
  botName: string;
}

/** 字幕消息列表：用户右侧、AI 左侧 */
export default function MessageList({ messages, botName }: MessageListProps) {
  const visible = messages.filter((m) => m.text.trim().length > 0);
  if (visible.length === 0) {
    return <div className="msg-empty">对话内容将实时显示在这里</div>;
  }
  return (
    <div className="msg-list">
      {visible.map((m) => (
        <div key={m.id} className={`msg-row ${m.role === 'ai' ? 'ai' : 'user'}`}>
          <div className={`msg-bubble ${m.final ? '' : 'interim'}`}>{m.text}</div>
        </div>
      ))}
    </div>
  );
}
