import React, { useEffect } from 'react';

function TestBackend() {
  useEffect(() => {
    fetch('/api/test')
      .then(response => response.json())
      .then(data => console.log(data))
      .catch(error => console.error('Error:', error));
  }, []);

  return <div>Test de connexion au backend</div>;
}

export default TestBackend;