import { createApp } from 'vue';

import SimpleHostTerminalPage from './components/terminal/SimpleHostTerminalPage.vue';
import { installNativeUi } from '@shared/ui/native';
import './styles/simple-host-terminal.css';
import './styles.css';
import '@xterm/xterm/css/xterm.css';

const app = createApp(SimpleHostTerminalPage);
installNativeUi(app);
app.mount('#host-terminal-app');
