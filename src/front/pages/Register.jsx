import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
export const Register = () => {
    const [first_name, setFirstName] = useState('')
    const [last_name, setLastName] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')

    const navigate = useNavigate()
    const handleRegister = async () => {
        try {
            const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}register`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    first_name: first_name,
                    last_name: last_name,
                    email: email,
                    password: password
                })
            })
            const data = await response.json()
            if (!response.ok) {
                throw new Error(data.msg)
            }
            navigate("/login")

        } catch (err) {
            setError(err.message)
        }
    }

    return (

        <form className="row g-3 container-form-sign-up"
            onSubmit={(e) => {
                e.preventDefault()
                handleRegister()
            }}
        >
            <div className="col-md-6">
                <label className="form-label">First Name</label>
                <input type="texte" className="form-control" id="inputEmail4"
                    onChange={(e) => setFirstName(e.target.value)} value={first_name} />
            </div>
            <div className="col-md-6">
                <label className="form-label">Last Name</label>
                <input className="form-control" id="inputPassword4"
                    onChange={(e) => setLastName(e.target.value)} value={last_name} />
            </div>
            <div className="col-12">
                <label className="form-label">Email</label>
                <input type="email" className="form-control"
                    onChange={(e) => setEmail(e.target.value)} value={email} />
            </div>
            <div className="col-12">
                <label className="form-label">Password</label>
                <input type="password" className="form-control"
                    onChange={(e) => setPassword(e.target.value)} value={password} />
            </div>
            <div>
                <p className="text-danger">{error}</p>
            </div>
            <div className="col-12">
                <button type="submit" className="btn btn-primary col-12">Sign Up</button>
            </div>
            <div className="login-form">
                <p>Already have in account
                    <Link to="/login">
                        <span className="navbar-brand mb-0 h1">    Login</span>
                    </Link>
                </p>
            </div>
        </form>

    )
}