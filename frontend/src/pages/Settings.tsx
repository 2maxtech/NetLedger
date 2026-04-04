import { useEffect } from 'react';
import {
  Card, Form, Input, InputNumber, Select, Button, Tabs, Typography, Space, message,
} from 'antd';
import { SettingOutlined, MailOutlined, MobileOutlined } from '@ant-design/icons';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  getSmtpSettings, saveSmtpSettings, testSmtp,
  getSmsSettings, saveSmsSettings, testSms,
} from '../api/settings';

const SmtpSettings = () => {
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['settings-smtp'],
    queryFn: () => getSmtpSettings().then((r) => r.data),
  });

  useEffect(() => {
    if (data) form.setFieldsValue(data);
  }, [data, form]);

  const saveMut = useMutation({
    mutationFn: saveSmtpSettings,
    onSuccess: () => message.success('SMTP settings saved'),
    onError: () => message.error('Failed to save settings'),
  });

  const testMut = useMutation({
    mutationFn: testSmtp,
    onSuccess: () => message.success('Test email sent successfully'),
    onError: () => message.error('Test email failed — check your settings'),
  });

  const onFinish = (values: any) => saveMut.mutate(values);

  const sendTest = () => {
    form
      .validateFields()
      .then((values) => testMut.mutate(values))
      .catch(() => {});
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={onFinish}
      initialValues={{ port: 587 }}
    >
      <Form.Item name="host" label="SMTP Host" rules={[{ required: true }]}>
        <Input placeholder="smtp.gmail.com" disabled={isLoading} />
      </Form.Item>
      <Form.Item name="port" label="Port" rules={[{ required: true }]}>
        <InputNumber style={{ width: '100%' }} disabled={isLoading} />
      </Form.Item>
      <Form.Item name="username" label="Username" rules={[{ required: true }]}>
        <Input disabled={isLoading} />
      </Form.Item>
      <Form.Item name="password" label="Password">
        <Input.Password placeholder="Leave blank to keep current" disabled={isLoading} />
      </Form.Item>
      <Form.Item name="from_email" label="From Email" rules={[{ required: true, type: 'email' }]}>
        <Input disabled={isLoading} />
      </Form.Item>
      <Form.Item name="from_name" label="From Name">
        <Input disabled={isLoading} />
      </Form.Item>
      <Space>
        <Button type="primary" htmlType="submit" loading={saveMut.isPending}>
          Save
        </Button>
        <Button onClick={sendTest} loading={testMut.isPending}>
          Send Test Email
        </Button>
      </Space>
    </Form>
  );
};

const SmsSettings = () => {
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['settings-sms'],
    queryFn: () => getSmsSettings().then((r) => r.data),
  });

  useEffect(() => {
    if (data) form.setFieldsValue(data);
  }, [data, form]);

  const saveMut = useMutation({
    mutationFn: saveSmsSettings,
    onSuccess: () => message.success('SMS settings saved'),
    onError: () => message.error('Failed to save settings'),
  });

  const testMut = useMutation({
    mutationFn: testSms,
    onSuccess: () => message.success('Test SMS sent successfully'),
    onError: () => message.error('Test SMS failed — check your settings'),
  });

  const onFinish = (values: any) => saveMut.mutate(values);

  const sendTest = () => {
    form
      .validateFields()
      .then((values) => testMut.mutate(values))
      .catch(() => {});
  };

  return (
    <Form form={form} layout="vertical" onFinish={onFinish}>
      <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
        <Select disabled={isLoading}>
          <Select.Option value="semaphore">Semaphore</Select.Option>
          <Select.Option value="vonage">Vonage</Select.Option>
          <Select.Option value="twilio">Twilio</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item name="api_key" label="API Key" rules={[{ required: true }]}>
        <Input.Password disabled={isLoading} />
      </Form.Item>
      <Form.Item name="sender_name" label="Sender Name">
        <Input disabled={isLoading} />
      </Form.Item>
      <Space>
        <Button type="primary" htmlType="submit" loading={saveMut.isPending}>
          Save
        </Button>
        <Button onClick={sendTest} loading={testMut.isPending}>
          Send Test SMS
        </Button>
      </Space>
    </Form>
  );
};

const Settings = () => {
  const tabItems = [
    {
      key: 'smtp',
      label: (
        <span>
          <MailOutlined /> Email (SMTP)
        </span>
      ),
      children: <SmtpSettings />,
    },
    {
      key: 'sms',
      label: (
        <span>
          <MobileOutlined /> SMS
        </span>
      ),
      children: <SmsSettings />,
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <SettingOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          Settings
        </Typography.Title>
      </div>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
};

export default Settings;
