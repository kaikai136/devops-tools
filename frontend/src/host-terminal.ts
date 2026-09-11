import { createApp } from 'vue';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';

import SimpleHostTerminalPage from './components/terminal/SimpleHostTerminalPage.vue';
import './styles/tokens.css';
import './styles/tailwind.css';
import './styles/base/element-plus-theme.css';
import './styles/base/element-plus-overrides.css';
import './styles/simple-host-terminal.css';
import '@xterm/xterm/css/xterm.css';

const app = createApp(SimpleHostTerminalPage);
app.use(ElementPlus);
app.mount('#host-terminal-app');
