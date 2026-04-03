import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Card, Input, Select, Button, Space, Modal, Form, Typography, message } from 'antd';
import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getCustomers, createCustomer } from '../../api/customers';
import { getPlans } from '../../api/plans';
import StatusTag from '../../components/StatusTag';
import dayjs from 'dayjs';

const CustomerList = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['customers', page, pageSize, search, statusFilter],
    queryFn: () => getCustomers({ page, page_size: pageSize, search: search || undefined, status: statusFilter }),
  });

  const { data: plansData } = useQuery({
    queryKey: ['plans-active'],
    queryFn: () => getPlans({ active_only: true }),
  });

  const createMutation = useMutation({
    mutationFn: createCustomer,
    onSuccess: () => {
      message.success('Customer created');
      setModalOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['customers'] });
    },
    onError: () => message.error('Failed to create customer'),
  });

  const columns = [
    { title: 'Name', dataIndex: 'full_name', key: 'name', render: (text: string, record: any) => <a onClick={() => navigate(`/customers/${record.id}`)}>{text}</a> },
    { title: 'Email', dataIndex: 'email', key: 'email' },
    { title: 'PPPoE User', dataIndex: 'pppoe_username', key: 'pppoe' },
    { title: 'Plan', key: 'plan', render: (_: any, record: any) => record.plan?.name || '-' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (status: string) => <StatusTag status={status} /> },
    { title: 'Created', dataIndex: 'created_at', key: 'created', render: (d: string) => dayjs(d).format('YYYY-MM-DD') },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>Customers</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Add Customer</Button>
      </div>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Input placeholder="Search..." prefix={<SearchOutlined />} value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} allowClear style={{ width: 250 }} />
          <Select placeholder="Status" value={statusFilter} onChange={(v) => { setStatusFilter(v); setPage(1); }} allowClear style={{ width: 150 }}>
            <Select.Option value="active">Active</Select.Option>
            <Select.Option value="suspended">Suspended</Select.Option>
            <Select.Option value="disconnected">Disconnected</Select.Option>
            <Select.Option value="terminated">Terminated</Select.Option>
          </Select>
        </Space>
        <Table
          dataSource={data?.data?.items}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ current: page, pageSize, total: data?.data?.total, onChange: (p, ps) => { setPage(p); setPageSize(ps); }, showSizeChanger: true, showTotal: (total) => `${total} customers` }}
        />
      </Card>

      <Modal title="Add Customer" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} confirmLoading={createMutation.isPending}>
        <Form form={form} layout="vertical" onFinish={(values) => createMutation.mutate(values)}>
          <Form.Item name="full_name" label="Full Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email' }]}><Input /></Form.Item>
          <Form.Item name="phone" label="Phone" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="address" label="Address"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="pppoe_username" label="PPPoE Username" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="pppoe_password" label="PPPoE Password" rules={[{ required: true }]}><Input.Password /></Form.Item>
          <Form.Item name="plan_id" label="Plan" rules={[{ required: true }]}>
            <Select placeholder="Select plan">
              {plansData?.data?.map((p: any) => <Select.Option key={p.id} value={p.id}>{p.name} — ₱{p.monthly_price}/mo</Select.Option>)}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default CustomerList;
