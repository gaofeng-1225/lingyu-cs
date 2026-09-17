import { useLayoutEffect, useRef } from 'react';
import { ChatMsg } from '../store/roomSlice';

interface MessageListProps {
  messages: ChatMsg[];
  botName: string;
}

/** 字幕消息列表：用户右侧、AI 左侧 */
export default function MessageList({ messages, botName }: MessageListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const followsLatestRef = useRef(true);
  const visible = messages.filter((m) => m.text.trim().length > 0);

  useLayoutEffect(() => {
    const list = listRef.current;
    if (list && followsLatestRef.current) {
      list.scrollTop = list.scrollHeight;
    }
  }, [messages]);

  if (visible.length === 0) {
    return <div className="msg-empty">对话内容将实时显示在这里</div>;
  }
  return (
    <div
      ref={listRef}
      className="msg-list"
      onScroll={(event) => {
        const list = event.currentTarget;
        followsLatestRef.current = list.scrollHeight - list.scrollTop - list.clientHeight <= 48;
      }}
    >
      {visible.map((m) => (
        <div key={m.id} className={`msg-row ${m.role === 'ai' ? 'ai' : 'user'}`}>
          <div className={`msg-bubble ${m.final ? '' : 'interim'}`}>{m.text}</div>
        </div>
      ))}
    </div>
  );
}
