import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Layout, Button, Dropdown, Space, Typography } from 'antd';
import { MenuFoldOutlined, MenuUnfoldOutlined, UserOutlined, LogoutOutlined } from '@ant-design/icons';
import SideMenu from './SideMenu';
import { useAuth } from '../../hooks/useAuth';

const { Header, Sider, Content } = Layout;

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(true);
  const { user, logout } = useAuth();

  const userMenuItems = [
    { key: 'user', label: `${user?.username} (${user?.role})`, disabled: true },
    { type: 'divider' as const },
    { key: 'logout', icon: <LogoutOutlined />, label: 'Logout', onClick: logout },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        width={220}
        collapsedWidth={64}
        style={{ background: '#0f172a', overflow: 'auto', height: '100vh', position: 'fixed', left: 0, top: 0, bottom: 0, zIndex: 100 }}
      >
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Typography.Text strong style={{ color: '#fff', fontSize: collapsed ? 18 : 16 }}>
            {collapsed ? '2M' : '2maXnetBill'}
          </Typography.Text>
        </div>
        <SideMenu />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 64 : 220, transition: 'margin-left 0.2s' }}>
        <Header style={{ background: '#fff', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #f0f0f0', position: 'sticky', top: 0, zIndex: 99 }}>
          <Button type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed(!collapsed)} />
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <UserOutlined />
              <span>{user?.username}</span>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, background: '#f5f5f5', minHeight: 'calc(100vh - 64px - 48px)' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
