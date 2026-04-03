import { useNavigate, useLocation } from 'react-router-dom';
import { Menu } from 'antd';
import type { MenuProps } from 'antd';
import {
  DashboardOutlined, TeamOutlined, AppstoreOutlined, WifiOutlined,
  FileTextOutlined, DollarOutlined, UserOutlined, DesktopOutlined, FileSearchOutlined,
} from '@ant-design/icons';

type MenuItem = Required<MenuProps>['items'][number];

const menuItems: MenuItem[] = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/customers', icon: <TeamOutlined />, label: 'Customers' },
  { key: '/plans', icon: <AppstoreOutlined />, label: 'Plans' },
  { key: '/pppoe', icon: <WifiOutlined />, label: 'PPPoE Sessions' },
  { key: 'billing', icon: <FileTextOutlined />, label: 'Billing', children: [
    { key: '/billing/invoices', icon: <FileTextOutlined />, label: 'Invoices' },
    { key: '/billing/payments', icon: <DollarOutlined />, label: 'Payments' },
  ]},
  { key: 'system', icon: <DesktopOutlined />, label: 'System', children: [
    { key: '/system/users', icon: <UserOutlined />, label: 'Staff Users' },
    { key: '/system/status', icon: <DesktopOutlined />, label: 'System Status' },
    { key: '/system/logs', icon: <FileSearchOutlined />, label: 'Logs' },
  ]},
];

const SideMenu = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const onClick: MenuProps['onClick'] = (e) => {
    navigate(e.key);
  };

  return (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[location.pathname]}
      defaultOpenKeys={['billing', 'system']}
      items={menuItems}
      onClick={onClick}
      style={{ borderRight: 0 }}
    />
  );
};

export default SideMenu;
