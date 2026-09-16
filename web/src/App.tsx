import { Routes, Route, Navigate } from 'react-router-dom';
import Home from './pages/Home';
import CallRoom from './pages/CallRoom';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/call/:sceneId" element={<CallRoom />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
