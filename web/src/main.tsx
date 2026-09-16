import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { store } from './store';
import './styles/global.css';

// 注：不启用 StrictMode——RTC 引擎生命周期与开发模式双挂载不兼容，
// 双挂载会导致重复创建/销毁引擎与状态竞态。
ReactDOM.createRoot(document.getElementById('root')!).render(
  <Provider store={store}>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </Provider>
);
