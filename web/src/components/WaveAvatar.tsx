interface WaveAvatarProps {
  name: string;
  talking: boolean;
  thinking: boolean;
  audioLevel: number;
}

/** AI 头像 + 音波动画 */
export default function WaveAvatar({ name, talking, thinking, audioLevel }: WaveAvatarProps) {
  const bars = Array.from({ length: 9 });
  const height = (index: number) => {
    if (!talking) return 8;
    const phase = ((index * 37) % 100) / 100;
    return Math.max(6, Math.min(46, 6 + audioLevel * 300 * (0.4 + phase) + Math.sin(Date.now() / 200 + index) * 8));
  };

  return (
    <div className="wave-avatar">
      <div className={`avatar-ring ${talking ? 'talking' : ''} ${thinking ? 'thinking' : ''}`}>
        <div className="avatar-core">聆</div>
      </div>
      <div className="wave-bars">
        {bars.map((_, i) => (
          <span key={i} className="wave-bar" style={{ height: `${height(i)}px` }} />
        ))}
      </div>
      <div className="avatar-name">{name}</div>
    </div>
  );
}
