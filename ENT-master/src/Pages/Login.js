import React from 'react'
import { Link } from 'react-router-dom'
import './Login.css'
import logo from '../Assets/logo.png'
import Switch from '../Components/Switch'
const Login = () => {
  return (
    <div className='container-login'>
        <div className='form-login-container'>
            <img src={logo} className='logo'/>
            <form className='form-login'>
              <p>Bienvenu</p>
              <div className='inputs-section-login'>
                <div>

                  {/*----- email -----*/}
                  <input type='email' placeholder='Saisir votre email institutionnel ' required/><br/>
                  {/*----- password -----*/}
                  <input type='password' placeholder='Saisir votre mot de passe ' required/>
                </div>
                  {/*----- rememeber me -----*/}
                <div className='Remember-me-section-login'>
                  <Switch></Switch>
                  <label>Se souvenir de moi </label>
                </div>

              </div>

                <div className='submit-section-login'>
                  <div>
                    <small><Link to='/signup'>Nouveau a l'universite ?</Link></small><br/>
                    <small><a href='#'>Mot de passe oublie</a></small>
                  </div>
                  <button>Se connecte</button>
                </div>
            </form>
        </div>
    </div>
  )
}

export default Login
