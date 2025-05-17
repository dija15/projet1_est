import React from 'react'
import './Home.css'
import Navbar from '../Components/Navbar'
import { FaEnvelope, FaClipboardList, FaCalendarAlt, FaWrench, FaLaptop, FaProjectDiagram } from 'react-icons/fa';

const Home = () => {
    const services = [
        {
          icon: <FaEnvelope />,
          title: 'Messagerie',
          description: "Messagerie électronique des étudiants de l’université",
        },
        {
          icon: <FaClipboardList />,
          title: 'Notes',
          description: 'Consulter vos notes aux épreuves',
        },
        {
          icon: <FaCalendarAlt />,
          title: 'Calendrier des examens',
          description: 'Consulter votre calendrier d’examens',
        },
        {
          icon: <FaWrench />,
          title: 'Demande d’intervention',
          description: 'Demandez une intervention technique',
        },
        {
          icon: <FaLaptop />,
          title: 'Cours en ligne',
          description: "Accéder à la plateforme pédagogique de l’université (Moodle)",
        },
        {
          icon: <FaProjectDiagram />,
          title: 'Assistance ENT',
          description: 'Faire aux questions sur l’environnement numérique de travail',
        },
        {
          icon: <FaProjectDiagram />,
          title: 'Assistance ENT',
          description: 'Faire aux questions sur l’environnement numérique de travail',
        },
        {
          icon: <FaProjectDiagram />,
          title: 'Assistance ENT',
          description: 'Faire aux questions sur l’environnement numérique de travail',
        },
        {
          icon: <FaProjectDiagram />,
          title: 'Assistance ENT',
          description: 'Faire aux questions sur l’environnement numérique de travail',
        },
        {
          icon: <FaProjectDiagram />,
          title: 'Assistance ENT',
          description: 'Faire aux questions sur l’environnement numérique de travail',
        },
      ];
    
      return (
        <div className="dashboard-container">
          <Navbar></Navbar>
    
          <div className="cards-container">
            {services.map((service,
             index) => (
              <div className="card" key={index}>
                <div className="icon-wrapper">{service.icon}</div>
                <h3>{service.title}</h3>
                <p>{service.description}</p>
              </div>
            ))}
          </div>
        </div>
  )
}

export default Home
