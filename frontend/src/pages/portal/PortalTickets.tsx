import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Card, Typography, Table, Button, Modal, Form, Input, Select, Space, Tag, message,
} from 'antd';
import { ArrowLeftOutlined, PlusOutlined, CustomerServiceOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import axios from 'axios';

const portalClient = axios.create({
  baseURL: '/api/v1/portal',
  headers: { 'Content-Type': 'application/json' },
});
portalClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('portal_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

const STATUS_COLORS: Record<string, string> = {
  open: '#3b82f6',
  in_progress: '#f59e0b',
  resolved: '#10b981',
  closed: '#6b7280',
};

const PortalTickets = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['portal-tickets'],
    queryFn: () => portalClient.get('/tickets').then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: (values: any) => portalClient.post('/tickets', values),
    onSuccess: (res) => {
      message.success('Ticket submitted');
      setModalOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['portal-tickets'] });
      navigate(`/portal/tickets/${res.data.id}`);
    },
    onError: () => message.error('Failed to submit ticket'),
  });

  const tickets: any[] = Array.isArray(data) ? data : (data?.items || []);

  const columns = [
    {
      title: '#',
      dataIndex: 'id',
      key: 'id',
      render: (id: string) => id.slice(0, 8),
      width: 90,
    },
    { title: 'Subject', dataIndex: 'subject', key: 'subject', ellipsis: true },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Tag color={STATUS_COLORS[s] || '#6b7280'}>{s.replace('_', ' ')}</Tag>
      ),
      width: 110,
    },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created',
      render: (d: string) => dayjs(d).format('YYYY-MM-DD'),
      width: 110,
    },
  ];

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Link to="/portal">
          <ArrowLeftOutlined /> Back to Dashboard
        </Link>
      </Space>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <CustomerServiceOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          My Tickets
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          Submit Ticket
        </Button>
      </div>
      <Card>
        <Table
          dataSource={tickets}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ pageSize: 20 }}
          onRow={(record: any) => ({
            onClick: () => navigate(`/portal/tickets/${record.id}`),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>

      <Modal
        title="Submit Support Ticket"
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        confirmLoading={createMut.isPending}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => createMut.mutate(values)}
          initialValues={{ priority: 'medium' }}
        >
          <Form.Item name="subject" label="Subject" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="priority" label="Priority">
            <Select>
              <Select.Option value="low">Low</Select.Option>
              <Select.Option value="medium">Medium</Select.Option>
              <Select.Option value="high">High</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="message" label="Message" rules={[{ required: true }]}>
            <Input.TextArea rows={5} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PortalTickets;
