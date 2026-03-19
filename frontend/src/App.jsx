import './App.css'

function App() {
  return (
    <div className="page">
      <header className="top-logo">
        <h1>
          MeTube <span className="logo-mark">◡̈</span>
        </h1>
      </header>

      <main className="login-wrapper">
        <div className="login-card">
          <div className="small-icon">🎵</div>

          <h2 className="welcome-text">Me too! 歡迎回來！</h2>

          <button className="google-btn">
            Continue with Google <span className="google-icon">G</span>
          </button>

          <p className="hint-text">本平台僅用 Google 帳號登入！</p>
        </div>

        <div className="bottom-area">
          <button className="other-btn">其他</button>
        </div>
      </main>
    </div>
  )
}

export default App