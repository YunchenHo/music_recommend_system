import { useNavigate } from "react-router-dom"
import "../styles/LoginPage.css"

function LoginPage() {
  const navigate = useNavigate()

  const handleGoogleLogin = () => {
    navigate("/register")
  }

  return (
    <div className="login-page">
      <header className="login-header">
        <h1 className="login-logo">
          MeTube <span className="logo-mark">◡̈</span>
        </h1>
      </header>

      <main className="login-container">
        <div className="login-card">
          <div className="login-icon">🎵</div>

          <h2 className="login-title">Me too! 歡迎回來！</h2>

          <button className="google-button" onClick={handleGoogleLogin}>
            Continue with Google
            <span className="google-circle">G</span>
          </button>

          <p className="login-hint">本平台僅用 Google 帳號登入！</p>
        </div>

        <div className="login-footer">
          <button className="other-button">其他</button>
        </div>
      </main>
    </div>
  )
}

export default LoginPage