import { useNavigate } from "react-router-dom"
import "../styles/LoginPage.css"

import { useEffect, useState } from "react"



function LoginPage() {
  const navigate = useNavigate()

  const handleGoogleLogin = () => {
    navigate("/register")
  }

  const rabbitFrames = [
    "/rabbit-1.png",
    "/rabbit-2.png",
    "/rabbit-3.png",
    "/rabbit-4.png",
    "/rabbit-5.png",
    "/rabbit-6.png",
  ]

  const [currentFrame, setCurrentFrame] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentFrame((prev) => (prev + 1) % rabbitFrames.length)
    }, 280)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="login-page">
      <header className="login-header">
        <h1 className="login-logo">
          <span>M</span>
          <span>e</span>
          <span>T</span>
          <span>u</span>
          <span>b</span>
          <span>e</span>  
          <img
            src="/yeah-rabbit.svg"
            alt="MeTube rabbit mascot"
            className="logo-image"
          />
        </h1>
      </header>

      <main className="login-container">
        <div className="login-card">
          {/*<div className="login-icon">🎵</div>*/}

          <h2 className="login-title">
            <span>M</span>
            <span>e</span>
            <span>&nbsp;</span>
            <span>t</span>
            <span>o</span>
            <span>o</span>
            <span>!</span>
            <span>&nbsp;</span>c
            <span>歡</span>
            <span>迎</span>
            <span>回</span>
            <span>來</span>
            <span>！</span>
          </h2>

          <button className="google-button" onClick={handleGoogleLogin}>
            Continue with Google
            <img
              src="/google-logo.svg"
              alt="Google logo"
              className="google-icon"
            />
          </button>

          <p className="login-hint">本平台僅用 Google 帳號登入！</p>
        </div>
        <div className="login-footer">    
            <img
              src={rabbitFrames[currentFrame]}
              alt="rabbit animation"
              className="footer-rabbit"
            />
        </div>


      </main>
    </div>
  )
}

export default LoginPage