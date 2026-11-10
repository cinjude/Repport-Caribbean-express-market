import { useEffect, useState } from "react"
import useGlobalReducer from "../hooks/useGlobalReducer"
import { useNavigate } from "react-router-dom"
const Private = () => {

  const { store } = useGlobalReducer()
  const [message, setMessage] = useState("")
  const navigate = useNavigate()

  useEffect(() => {
    const token = localStorage.getItem("token")

    fetch(`${import.meta.env.VITE_BACKEND_URL}private`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    })
      .then(res => res.json())
      .then(data => setMessage(data.msg))
  }, [])
  return (

    <div>
      {
        !store.token ?
          navigate("login")
          :
          (
            <div>
              <p>private page</p>
              <p className="bg-primary text-light"> {message} </p>
            </div>
          )
      }
    </div>

  )
}
export default Private