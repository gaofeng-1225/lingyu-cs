import { CallStatus } from '../store/roomSlice';

interface ControlBarProps {
  status: CallStatus;
  joining: boolean;
  muted: boolean;
  canInterrupt: boolean;
  onStart: () => void;
  onMute: () => void;
  onInterrupt: () => void | Promise<void>;
  onEnd: () => void;
}

export default function ControlBar({
  status,
  joining,
  muted,
  canInterrupt,
  onStart,
  onMute,
  onInterrupt,
  onEnd,
}: ControlBarProps) {
  if (status === 'idle' || status === 'connecting') {
    return (
      <footer className="control-bar">
        <button className="btn-primary" onClick={onStart} disabled={joining || status === 'connecting'}>
          {joining || status === 'connecting' ? '连接中…' : '开始通话'}
        </button>
        <p className="control-hint">需要麦克风权限；请使用 Chrome / Edge 浏览器（localhost 或 HTTPS）</p>
      </footer>
    );
  }

  return (
    <footer className="control-bar">
      <div className="control-group">
        <button className="btn-round" title={muted ? '取消静音' : '静音'} onClick={onMute}>
          {muted ? '🔇' : '🎙️'}
        </button>
        <button
          className={`btn-interrupt ${canInterrupt ? 'active' : ''}`}
          onClick={() => void onInterrupt()}
          disabled={!canInterrupt}
          title="打断 AI"
        >
          ⏸ 打断
        </button>
        <button className="btn-end" onClick={onEnd}>
          结束通话
        </button>
      </div>
    </footer>
  );
}
