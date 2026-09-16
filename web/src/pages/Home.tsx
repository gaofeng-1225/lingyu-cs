import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, GetScenesResult } from '../api/client';

const SESSION_KEY = 'lingyu_session';

export function saveSession(data: GetScenesResult['Result']) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
}

export function loadSession(): GetScenesResult['Result'] | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as GetScenesResult['Result']) : null;
  } catch {
    return null;
  }
}

export default function Home() {
  const navigate = useNavigate();
  const [result, setResult] = useState<GetScenesResult['Result'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .getScenes()
      .then((data) => {
        setResult(data.Result);
        saveSession(data.Result);
        setError('');
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const enter = (sceneId: string) => {
    if (!result) return;
    navigate(`/call/${sceneId}`);
  };

  return (
    <div className="home">
      <header className="brand">
        <div className="brand-logo">聆</div>
        <div>
          <h1>聆语智服</h1>
          <p>AI 语音智能客服 · 实时对话</p>
        </div>
      </header>

      <section className="hero">
        <h2>选择服务场景，即刻开始语音对话</h2>
        <p className="hero-sub">低延迟实时语音 · RAG 知识库精准回答 · 支持随时打断</p>
      </section>

      {loading && <div className="loading">正在连接服务端…</div>}

      {error && (
        <div className="error-box">
          <p>无法获取场景列表：{error}</p>
          <p className="error-hint">
            请确认服务端已启动（server 目录 <code>python run.py</code>），并已配置
            <code> server/.env</code>。
          </p>
        </div>
      )}

      {!loading && !error && (
        <div className="scene-grid">
          {result?.scenes.map(({ scene }) => (
            <button key={scene.id} className="scene-card" onClick={() => enter(scene.id)}>
              <div className="scene-icon">
                {scene.icon ? <img src={scene.icon} alt="" /> : '聆'}
              </div>
              <h3>{scene.name}</h3>
              <ul className="scene-questions">
                {scene.questions?.slice(0, 2).map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
              <span className="scene-enter">进入通话 →</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
