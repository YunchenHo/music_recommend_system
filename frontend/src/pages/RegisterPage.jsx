import { useState } from "react"
import { useNavigate } from "react-router-dom"
import "../styles/RegisterPage.css"

function RegisterPage() {
  const navigate = useNavigate()

  const [nickname, setNickname] = useState("")
  const [gender, setGender] = useState("")
  const [age, setAge] = useState("")
  const [languages, setLanguages] = useState([])
  const [otherLanguage, setOtherLanguage] = useState("")
  const [activeError, setActiveError] = useState(null)

  const clearActiveError = (fieldName) => {
    if (activeError?.field === fieldName) {
      setActiveError(null)
    }
  }

  const handleLanguageChange = (language) => {
    if (languages.includes(language)) {
      setLanguages(languages.filter((item) => item !== language))
    } else {
      setLanguages([...languages, language])
    }

    if (
      activeError?.field === "languages" ||
      activeError?.field === "otherLanguage"
    ) {
      setActiveError(null)
    }
  }

  const validateForm = () => {
    const trimmedNickname = nickname.trim()
    const trimmedOtherLanguage = otherLanguage.trim()
    const ageNumber = Number(age)

    if (!trimmedNickname) {
      return { field: "nickname", message: "請輸入名稱" }
    }

    if (trimmedNickname && !/^[a-zA-Z0-9]+$/.test(trimmedNickname)) {
      return { field: "nickname", message: "名稱只能包含英數字元" }
    }

    if (trimmedNickname.length > 16 ) {
      return { field: "nickname", message: "名稱長度需為 1 到 16 個字元" }
    }

    if (!gender) {
      return { field: "gender", message: "請選擇性別" }
    }

    if (age === "") {
      return { field: "age", message: "請輸入年齡" }
    }

    if (!Number.isInteger(ageNumber) || ageNumber < 0 || ageNumber > 150) {
      return { field: "age", message: "年齡需介於 0 到 150 歲" }
    }

    if (languages.length === 0) {
      return { field: "languages", message: "請至少選擇一種喜好語言" }
    }

    if (languages.includes("其他") && !trimmedOtherLanguage) {
      return { field: "otherLanguage", message: "請填寫其他偏好語言" }
    }

    if (languages.includes("其他") && !/^[\u4e00-\u9fa5]+$/.test(trimmedOtherLanguage)) {
      return { field: "otherLanguage", message: "請輸入中文" }
    }

    return null
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    const firstError = validateForm()

    if (firstError) {
      setActiveError(firstError)
      return
    }

    setActiveError(null)
    navigate("/home")
  }

  return (
    <div className="register-page">
      <header className="register-header">
        <h1 className="register-logo">
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

      <main className="register-container">
        <form className="register-card" onSubmit={handleSubmit}>
          <h2 className="register-title">
            <span>M</span>
            <span>e</span>
            <span> </span>
            <span>t</span>
            <span>o</span>
            <span>o</span>
            <span>!</span>
            <span>&nbsp;</span>
            <span> </span>
            <span>我</span>
            <span>要</span>
            <span>加</span>
            <span>入</span>
            <span>！</span>
          </h2>

          <div className="form-group form-row">
            <label className="form-label" htmlFor="nickname">
              * 名稱：
            </label>

            <div className="input-area">
              <input
                id="nickname"
                type="text"
                className="form-input"
                value={nickname}
                onChange={(e) => {
                  setNickname(e.target.value)
                  clearActiveError("nickname")
                }}
                placeholder="請輸入名稱（長度為 1 到 16 的英數字元）"
                maxLength={16}
              />

              {activeError?.field === "nickname" && (
                <div className="error-bubble">{activeError.message}</div>
              )}
            </div>
          </div>

          <div className="form-group form-row">
            <p className="form-label">* 性別：</p>

            <div className="input-area">
              <div className="radio-group">
                <label className="option-label">
                  <input
                    type="radio"
                    name="gender"
                    value="男"
                    checked={gender === "男"}
                    onChange={(e) => {
                      setGender(e.target.value)
                      clearActiveError("gender")
                    }}
                  />
                  男
                </label>

                <label className="option-label">
                  <input
                    type="radio"
                    name="gender"
                    value="女"
                    checked={gender === "女"}
                    onChange={(e) => {
                      setGender(e.target.value)
                      clearActiveError("gender")
                    }}
                  />
                  女
                </label>

                <label className="option-label">
                  <input
                    type="radio"
                    name="gender"
                    value="其他"
                    checked={gender === "其他"}
                    onChange={(e) => {
                      setGender(e.target.value)
                      clearActiveError("gender")
                    }}
                  />
                  其他
                </label>
              </div>

              {activeError?.field === "gender" && (
                <div className="error-bubble">{activeError.message}</div>
              )}
            </div>
          </div>

          <div className="form-group form-row">
            <label className="form-label" htmlFor="age">
              * 年齡：
            </label>

            <div className="input-area">
              <input
                id="age"
                type="number"
                className="form-input age-input"
                value={age}
                onChange={(e) => {
                  setAge(e.target.value)
                  clearActiveError("age")
                }}
                placeholder="請輸入年齡"
              />

              {activeError?.field === "age" && (
                <div className="error-bubble">{activeError.message}</div>
              )}
            </div>
          </div>

          <div className="form-group form-row">
            <p className="form-label">* 喜好的語言：</p>

            <div className="input-area">
              <div className="checkbox-group language-main-row">
                <label className="option-label">
                  <input
                    type="checkbox"
                    checked={languages.includes("中文")}
                    onChange={() => handleLanguageChange("中文")}
                  />
                  中文
                </label>

                <label className="option-label">
                  <input
                    type="checkbox"
                    checked={languages.includes("英文")}
                    onChange={() => handleLanguageChange("英文")}
                  />
                  英文
                </label>

                <label className="option-label">
                  <input
                    type="checkbox"
                    checked={languages.includes("韓文")}
                    onChange={() => handleLanguageChange("韓文")}
                  />
                  韓文
                </label>

                <label className="option-label">
                  <input
                    type="checkbox"
                    checked={languages.includes("日文")}
                    onChange={() => handleLanguageChange("日文")}
                  />
                  日文
                </label>
              </div>

              <div className="other-language-row">
                <label className="option-label other-option">
                  <input
                    type="checkbox"
                    checked={languages.includes("其他")}
                    onChange={() => handleLanguageChange("其他")}
                  />
                  其他：
                </label>

                <div className="other-language-inline">
                  <input
                    type="text"
                    className="form-input other-language-input"
                    value={otherLanguage}
                    onChange={(e) => {
                      setOtherLanguage(e.target.value)
                      clearActiveError("otherLanguage")
                    }}
                    placeholder="例如：德"
                    disabled={!languages.includes("其他")}
                  />
                  <span className="other-language-suffix">文</span>
                </div>
              </div>

              {(activeError?.field === "languages" ||
                activeError?.field === "otherLanguage") && (
                <div className="error-bubble">{activeError.message}</div>
              )}
            </div>
          </div>

          <button type="submit" className="submit-button">
            繼續
          </button>
        </form>
      </main>
    </div>
  )
}

export default RegisterPage