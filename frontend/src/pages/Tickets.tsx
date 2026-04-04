import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table, Card, Button, Modal, Form, Input, Select,
  Typography, Space, message, Tag,
} from 'antd';
import { PlusOutlined, CustomerServiceOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { getTickets, createTicket, type TicketType } from '../api/tickets';
import { getCustomers } from '../api/customers';

const STATUS_COLORS: Record<string, string> = {
  open: '#3b82f6',
  in_progress: '#f59e0b',
  resolved: '#10b981',
  closed: '#6b7280',
};

const PRIORITY_COLORS: Record<string, string> = {
  low: '#6b7280',
  medium: '#f59e0b',
  high: '#ef4444',
  urgent: '#dc2626',
};

const Tickets = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [priorityFilter, setPriorityFilter] = useState<string | undefined>();
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['tickets', statusFilter, priorityFilter],
    queryFn: () =>
      getTickets({
        status: statusFilter,
        priority: priorityFilter,
      }).then((r) => r.data),
  });

  const { data: customersData } = useQuery({
    queryKey: ['customers-all'],
    queryFn: () => getCustomers({ page: 1, page_size: 200 }),
  });

  const createMut = useMutation({
    mutationFn: createTicket,
    onSuccess: (res) => {
      message.success('Ticket created');
      setModalOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
      navigate(`/tickets/${res.data.id}`);
    },
    onError: () => message.error('Failed to create ticket'),
  });

  const customers = customersData?.data?.items || [];

  const columns = [
    {
      title: '#',
      dataIndex: 'id',
      key: 'id',
      render: (id: string) => id.slice(0, 8),
      width: 90,
    },
    {
      title: 'Customer',
      dataIndex: 'customer_id',
      key: 'customer',
      render: (cid: string) => {
        const c = customers.find((x: any) => x.id === cid);
        return c ? c.full_name : cid.slice(0, 8) + '...';
      },
    },
    { title: 'Subject', dataIndex: 'subject', key: 'subject', ellipsis: true },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag color={STATUS_COLORS[s] || '#6b7280'}>{s.replace('_', ' ')}</Tag>,
      width: 110,
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      render: (p: string) => <Tag color={PRIORITY_COLORS[p] || '#6b7280'}>{p}</Tag>,
      width: 90,
    },
    {
      title: 'Assigned To',
      dataIndex: 'assigned_to',
      key: 'assigned',
      render: (v: string | null) => v || '-',
      width: 130,
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
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <CustomerServiceOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          Support Tickets
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          New Ticket
        </Button>
      </div>

      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            placeholder="Filter by status"
            allowClear
            style={{ width: 160 }}
            value={statusFilter}
            onChange={setStatusFilter}
          >
            <Select.Option value="open">Open</Select.Option>
            <Select.Option value="in_progress">In Progress</Select.Option>
            <Select.Option value="resolved">Resolved</Select.Option>
            <Select.Option value="closed">Closed</Select.Option>
          </Select>
          <Select
            placeholder="Filter by priority"
            allowClear
            style={{ width: 160 }}
            value={priorityFilter}
            onChange={setPriorityFilter}
          >
            <Select.Option value="low">Low</Select.Option>
            <Select.Option value="medium">Medium</Select.Option>
            <Select.Option value="high">High</Select.Option>
            <Select.Option value="urgent">Urgent</Select.Option>
          </Select>
        </Space>
        <Table
          dataSource={data || []}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ pageSize: 20, showTotal: (t) => `${t} tickets` }}
          onRow={(record: TicketType) => ({
            onClick: () => navigate(`/tickets/${record.id}`),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>

      <Modal
        title="New Ticket"
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
          <Form.Item name="customer_id" label="Customer" rules={[{ required: true }]}>
            <Select
              showSearch
              placeholder="Search customer"
              filterOption={(input, option) =>
                String(option?.children ?? '').toLowerCase().includes(input.toLowerCase())
              }
            >
              {customers.map((c: any) => (
                <Select.Option key={c.id} value={c.id}>
                  {c.full_name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="subject" label="Subject" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="priority" label="Priority" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="low">Low</Select.Option>
              <Select.Option value="medium">Medium</Select.Option>
              <Select.Option value="high">High</Select.Option>
              <Select.Option value="urgent">Urgent</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="message" label="Initial Message" rules={[{ required: true }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Tickets;
