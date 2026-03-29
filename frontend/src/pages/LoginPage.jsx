import { useNavigate } from "react-router-dom"
import "../styles/LoginPage.css"
import { googleLogin } from "../api/auth"
import { useEffect, useState, useRef } from "react"

function LoginPage() {
  const navigate = useNavigate()
  const googleBtnRef = useRef(null)
  const googleInitialized = useRef(false)

  const rabbitFrames = [
    "/rabbit-1.png",
    "/rabbit-2.png",
    "/rabbit-3.png",
    "/rabbit-4.png",
    "/rabbit-5.png",
    "/rabbit-6.png",
  ]

  const [currentFrame, setCurrentFrame] = useState(0)

  const handleGoogleLogin = async (idToken) => {
    try {
      const res = await googleLogin(idToken)
      const profileCompleted = res?.data?.profile_completed

      if (profileCompleted === true || profileCompleted === 1) {
        navigate("/home")
      } else {
        navigate("/register")
      }
    } catch (error) {
      const err = error?.response?.data

      if (err?.code === "INVALID_GOOGLE_TOKEN") {
        alert("Google authentication failed. Please try again.")
      } else if (err?.code === "INVALID_DOMAIN") {
        alert("Only NYCU school emails are allowed.")
      } else {
        alert(err?.message || "Login failed.")
      }
    }
  }

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentFrame((prev) => (prev + 1) % rabbitFrames.length)
    }, 280)

    return () => clearInterval(interval)
  }, [rabbitFrames.length])

  useEffect(() => {
    const initGoogle = () => {
      if (window.google && googleBtnRef.current && !googleInitialized.current) {
        googleInitialized.current = true

        window.google.accounts.id.initialize({
          client_id:
            "294550145072-n13kla2nri1hc3k3vfjel9je6rqs3l3b.apps.googleusercontent.com",
          callback: (response) => {
            handleGoogleLogin(response.credential)
          },
        })

        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: "outline",
          size: "large",
          text: "continue_with",
          width: 360,
        })
      }
    }

    if (window.google) {
      initGoogle()
    } else {
      const timer = setInterval(() => {
        if (window.google) {
          clearInterval(timer)
          initGoogle()
        }
      }, 100)

      return () => clearInterval(timer)
    }
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
          <h2 className="login-title">
            <span>M</span>
            <span>e</span>
            <span>&nbsp;</span>
            <span>t</span>
            <span>o</span>
            <span>o</span>
            <span>!</span>
            <span>&nbsp;</span>
            <span>歡</span>
            <span>迎</span>
            <span>回</span>
            <span>來</span>
            <span>！</span>
          </h2>

          <div className="google-button-wrapper">
            <button type="button" className="google-button">
              Continue with Google
              <img
                src="/google-logo.svg"
                alt="Google logo"
                className="google-icon"
              />
            </button>

            <div ref={googleBtnRef} className="google-button-overlay"></div>
          </div>

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