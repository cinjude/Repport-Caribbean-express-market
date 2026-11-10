import { Link, useNavigate } from "react-router-dom";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faUser } from "@fortawesome/free-regular-svg-icons";
import useGlobalReducer from "../hooks/useGlobalReducer";
export const Navbar = () => {

	const navigate = useNavigate()
	const { store, dispatch } = useGlobalReducer()

	const handleLogout = () => {
		localStorage.removeItem("token")
		localStorage.removeItem("user")
		dispatch({type: "logout"})
		navigate("/login")
	}
	return (
		<nav className="navbar navbar-light bg-light">
			<div className="container">
				<Link to="/">
					<span className="navbar-brand mb-0 h1">React Boilerplate</span>
				</Link>
				<div className="dropdown dropdown-user-container">
					<button className="btn btn-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
						<div className="dropdown-user">
							<div className="icon">
								<FontAwesomeIcon icon={faUser} />
							</div>
							<div className="user">
								<span> {store.user? store.user : "Sign in" } </span>
								<p>Account</p>
							</div>
						</div>
					</button>
					<ul className="dropdown-menu">
						{
							store.token ? (
								<>
									<button className="link-logout" onClick={handleLogout}>Log Out</button>
								</>
							)
								:
								(
									<>
										<Link className="dropdown-item link-dropdown" to="login" >
											<span> Sign in or Create an account </span>
										</Link>
									</>
								)
						}
					</ul>
				</div>
			</div>
		</nav>
	);
};