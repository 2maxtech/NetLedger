import type { ThemeConfig } from 'antd';

const theme: ThemeConfig = {
  token: {
    colorPrimary: '#e8700a',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    colorInfo: '#e8700a',
    colorBgContainer: '#ffffff',
    colorBgLayout: '#f5f3f0',
    borderRadius: 8,
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  },
  components: {
    Layout: {
      siderBg: '#1c1306',
      headerBg: '#ffffff',
    },
    Menu: {
      darkItemBg: '#1c1306',
      darkSubMenuItemBg: '#1c1306',
      darkItemSelectedBg: 'rgba(232, 112, 10, 0.2)',
      darkItemSelectedColor: '#f9a825',
      darkItemHoverBg: 'rgba(255, 255, 255, 0.05)',
    },
    Table: {
      headerBg: '#faf8f5',
      headerColor: '#475569',
      rowHoverBg: '#fdf8f3',
      borderColor: '#e8e0d8',
    },
    Card: {
      borderRadiusLG: 12,
    },
    Button: {
      borderRadius: 6,
    },
    Input: {
      borderRadius: 6,
    },
    Select: {
      borderRadius: 6,
    },
  },
};

export default theme;
