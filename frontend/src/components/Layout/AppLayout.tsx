import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Layout, Button, Dropdown, Space, Avatar } from 'antd';
import { MenuFoldOutlined, MenuUnfoldOutlined, LogoutOutlined } from '@ant-design/icons';
import SideMenu from './SideMenu';
import { useAuth } from '../../hooks/useAuth';
import logoIcon from '../../assets/logo.png';

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
        style={{
          background: '#1c1306',
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          padding: collapsed ? 8 : '8px 16px',
          transition: 'all 0.2s',
          overflow: 'hidden',
        }}>
          <img
            src={logoIcon}
            alt="NetLedger"
            style={{
              height: collapsed ? 36 : 32,
              objectFit: 'contain',
              transition: 'all 0.2s',
            }}
          />
          {!collapsed && (
            <span style={{
              color: '#e2e8f0',
              fontSize: 18,
              fontWeight: 700,
              letterSpacing: '-0.5px',
              whiteSpace: 'nowrap',
              fontFamily: "'Inter', sans-serif",
            }}>
              NetLedger
            </span>
          )}
        </div>
        <SideMenu />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 64 : 220, transition: 'margin-left 0.2s' }}>
        <Header style={{
          background: '#ffffff',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
          position: 'sticky',
          top: 0,
          zIndex: 99,
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ color: '#475569' }}
          />
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space style={{ cursor: 'pointer', color: '#475569' }}>
              <Avatar
                size={32}
                style={{ background: 'rgba(232,112,10,0.12)', color: '#e8700a', fontSize: 13, fontWeight: 600 }}
              >
                {user?.username?.[0]?.toUpperCase() ?? 'U'}
              </Avatar>
              <span style={{ fontSize: 13, fontWeight: 500 }}>{user?.username}</span>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, minHeight: 'calc(100vh - 64px - 48px)' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
