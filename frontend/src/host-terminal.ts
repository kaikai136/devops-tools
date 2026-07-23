import { createApp } from 'vue';

import SimpleHostTerminalPage from './components/terminal/SimpleHostTerminalPage.vue';
import './styles/simple-host-terminal.css';
import '@xterm/xterm/css/xterm.css';

createApp(SimpleHostTerminalPage).mount('#host-terminal-app');
