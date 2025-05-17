import React from 'react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import './Signup.css'
import logo from '../Assets/logo.png'
import Switch from '../Components/Switch'
import { FaEye, FaEyeSlash } from 'react-icons/fa'

const Signup = () => {
    const [Show,setShow]=useState(false)
    const [InputType,setInputType]=useState(false)
        
    const toggleIcon=()=>{
        setShow(!Show)
        setInputType(!InputType)
        
    }
  return (
    <div className='container'>
        <div className='form-container-signup'>

            <img src={logo} className='logo'/>

            <form className='form-signup'>
                <p>Activation du compte étudiant</p>

                <div className='signup-inputs'>
                    {/*----- Numero d'inscription -----*/}
                    <input type='text' placeholder={`saisir votre Nº d'inscription`} required/>
                    {/*----- CIN / code massar -----*/}
                    <input type='text' placeholder='saisir votre CIN/code massar' required/>
                    {/*----- Date naissance -----*/}
                    <input type='date' placeholder=' saisir votre date de naissance' required/>
                    {/*----- Telephone -----*/}
                    <input type='phone' placeholder='saisir votre Nº de telephone' required/>
                    {/*----- Mot de passe -----*/}
                    <div className='showOrhide'>
                        <input type={InputType?'text':'password'} placeholder='saisir votre mot de passe ' required/>
                        <span className='icon' onClick={()=>{toggleIcon()}}>
                                    {Show?<FaEye></FaEye>:<FaEyeSlash></FaEyeSlash>}
                        </span>
                    </div>
                    {/*----- confirmation de mot de passe -----*/}
                    <input type='password' placeholder='saisir votre mot de passe' required/>
                </div>

                <div className='Remember-me-section-signup'>
                    <Switch></Switch>
                    <label>Se souvenir de moi</label>
                </div>

                <div className='submit-section-signup'>
                    <div>
                        <small><Link to='/login'>j'ai deja un compte</Link></small><br/>
                        <small><a href='#'>Mot de passe oublie</a></small>
                    </div>
                    <button>submit</button>
                </div>
            </form>
        </div>
      
    </div>
  )
}

export default Signup
