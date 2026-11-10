import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import useGlobalReducer from "../hooks/useGlobalReducer.jsx";
const Login = () => {
    const { dispatch } = useGlobalReducer()
    const navigate = useNavigate()

    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState(null)

    const handleLogin = async () => {
        try {
            console.log("EMAIL:", email);
            console.log("PASSWORD:", password);

            const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}login`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        email: email,
                        password: password
                    })
                })
            const data = await response.json()
            if (!response.ok) {
                throw new Error(data.msg)
            }
            localStorage.setItem("token", data.token)
            localStorage.setItem("user", email)

            dispatch({
                type: "login",
                payload: {
                    token: data.token,
                    user: email
                }
            })
            navigate("/private")

        } catch (err) {
            setError(err.message)
        }
    }

    return (
        <form className="container-form"
            onSubmit={(e) => {
                e.preventDefault()
                handleLogin()
            }}
        >
            <div className="mb-3">
                <label className="form-label">Email</label>
                <input type="text" className="form-control" placeholder="Enter your email"
                    onChange={(e) => setEmail(e.target.value)} value={email} />
            </div>
            <div className="mb-3">
                <label className="form-label">Password</label>
                <input type="text" className="form-control" placeholder="Password"
                    onChange={(e) => setPassword(e.target.value)} value={password} />
            </div>
            <div>
                <p className="text-danger">{error}</p>
            </div>
            <button type="submit" className="form-control btn btn-primary ">Login</button>
            <div className="login-form">
                <p>If you don't have an account
                    <Link to="/register">
                        <span className="navbar-brand mb-0 h1">    Sign Up</span>
                    </Link>
                </p>
            </div>
        </form>
    )
}
export default Login