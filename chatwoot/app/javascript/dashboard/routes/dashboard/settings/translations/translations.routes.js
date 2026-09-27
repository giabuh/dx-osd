import { frontendURL } from '../../../../helper/URLHelper';
import SettingsWrapper from '../SettingsWrapper.vue';
import Index from './Index.vue';

export default {
  routes: [
    {
      path: frontendURL('accounts/:accountId/settings/translations'),
      component: SettingsWrapper,
      props: { keepAlive: false },
      children: [
        {
          path: '',
          name: 'settings_vietnamese_translations',
          component: Index,
          meta: { permissions: ['administrator'] },
        },
      ],
    },
  ],
};
