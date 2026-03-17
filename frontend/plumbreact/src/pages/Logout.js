// src/pages/Logout.js
import { useEffect, useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import { useHistory } from "react-router-dom";

export default function Logout() {
  const { logout } = useContext(AuthContext);
  const history = useHistory();

  useEffect(() => {
    logout().then(() => history.push("/"));
  }, [logout, history]);

  // useEffect(() => {
  //   logout().then(() => {
  //     history.push("/login");
  //     window.location.reload();  // Релоад для повного очищення
  //   });
  // }, [logout, history]);

  return <div>Выход...</div>;
}