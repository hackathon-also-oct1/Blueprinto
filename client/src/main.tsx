import { createRoot } from 'react-dom/client';

import { App } from './App';
import './blueprint/blueprint.css';

// No StrictMode: its dev-only double mount connects to the bot twice, and the
// aborted first connection leaves an Anam avatar session open, which blocks the
// second one on plans with a single concurrent session.
createRoot(document.getElementById('root')!).render(<App />);
