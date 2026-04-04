import { useState } from 'react';
import { Card, Form, Input, Button, Typography, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { portalLogin } from '../../api/portal';
import logo from '../../assets/logo.png';

const PortalLogin = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { email: string; password: string }) => {
    setLoading(true);
    try {
      const res = await portalLogin(values.email, values.password);
      localStorage.setItem('portal_token', res.data.access_token);
      localStorage.setItem('portal_customer', JSON.stringify(res.data.customer));
      navigate('/portal');
    } catch {
      message.error('Invalid email or password');
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
          <Typography.Title level={4} style={{ margin: '0 0 4px' }}>Customer Portal</Typography.Title>
          <Typography.Text type="secondary">Sign in to your account</Typography.Text>
        </div>
        <Form onFinish={onFinish} layout="vertical" size="large">
          <Form.Item name="email" rules={[{ required: true, message: 'Enter your email' }]}>
            <Input prefix={<UserOutlined style={{ color: '#94a3b8' }} />} placeholder="Email address" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: 'Enter your password' }]}>
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

export default PortalLogin;
