import { createApp } from 'vue';

import App from './App.vue';
import { installNativeUi } from '@shared/ui/native';
import './styles.css';

const app = createApp(App);
installNativeUi(app);
app.mount('#app');
