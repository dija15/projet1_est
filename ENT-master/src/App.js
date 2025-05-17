import TestBackend from './Components/TestBackend';
import './App.css';
import Login from './Pages/Login';
import Footer from './Components/Footer';
import { Route, Routes } from 'react-router-dom';
import Signup from './Pages/Signup';
import Home from './Pages/Home';
import Chat from './Components/Chat';
import { useEffect } from 'react';

function App() {
  useEffect(() => {
    const handleScroll = () => {
      const message = document.getElementById('bottomMessage');
      if (message) {
        const { scrollY: scrollTop, innerHeight: windowHeight } = window;
        const { scrollHeight: pageHeight } = document.documentElement;
        
        // 50px de marge pour le déclenchement
        const shouldShow = scrollTop + windowHeight >= pageHeight - 50;
        message.style.display = shouldShow ? 'block' : 'none';
      }
    };

    window.addEventListener('scroll', handleScroll);
    
    // Nettoyage à la destruction du composant
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="App" role="main">
      <TestBackend />
      
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/chat" element={<Chat />} />
      </Routes>
      
      <div id="bottomMessage" aria-live="polite">
        <Footer />
      </div>
    </div>
  );
}

export default App;