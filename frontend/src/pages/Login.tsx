import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Card, Form, Input, Button, Typography, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useAuth } from '../hooks/useAuth';
import logo from '../assets/logo.png';

const Login = () => {
  const { login, isAuthenticated, isLoading } = useAuth();
  const [loading, setLoading] = useState(false);

  if (isLoading) return null;
  if (isAuthenticated) return <Navigate to="/" replace />;

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values);
    } catch {
      message.error('Invalid username or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #1c1306 0%, #3d2a0a 50%, #1c1306 100%)',
    }}>
      <Card
        style={{
          width: 400,
          borderRadius: 16,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          background: 'rgba(255, 255, 255, 0.98)',
        }}
        styles={{ body: { padding: '40px 32px' } }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <img src={logo} alt="NetLedger" style={{ height: 48, marginBottom: 12, objectFit: 'contain' }} />
          <Typography.Title level={4} style={{ margin: 0, color: '#1c1306' }}>
            Admin Portal
          </Typography.Title>
          <Typography.Text type="secondary">Sign in to manage your network</Typography.Text>
        </div>
        <Form onFinish={onFinish} layout="vertical" size="large">
          <Form.Item name="username" rules={[{ required: true, message: 'Enter username' }]}>
            <Input prefix={<UserOutlined style={{ color: '#94a3b8' }} />} placeholder="Username" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: 'Enter password' }]}>
            <Input.Password prefix={<LockOutlined style={{ color: '#94a3b8' }} />} placeholder="Password" />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            loading={loading}
            style={{ height: 44, fontSize: 15, borderRadius: 8 }}
          >
            Sign In
          </Button>
        </Form>
      </Card>
    </div>
  );
};

export default Login;
