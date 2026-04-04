import { useState } from 'react';
import {
  Table, Card, Button, Modal, Form, Input, InputNumber, Select,
  Typography, Popconfirm, Space, message, Tag, Alert,
} from 'antd';
import { PlusOutlined, DeleteOutlined, TagsOutlined, GiftOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import {
  getVouchers, generateVouchers, redeemVoucher, revokeVoucher,
  type VoucherType,
} from '../api/vouchers';
import { getPlans } from '../api/plans';
import { getCustomers } from '../api/customers';

const STATUS_COLORS: Record<string, string> = {
  unused: '#e8700a',
  active: '#10b981',
  expired: '#9ca3af',
  revoked: '#ef4444',
};

const Vouchers = () => {
  const queryClient = useQueryClient();
  const [generateOpen, setGenerateOpen] = useState(false);
  const [redeemOpen, setRedeemOpen] = useState(false);
  const [generatedCodes, setGeneratedCodes] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [genForm] = Form.useForm();
  const [redeemForm] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['vouchers', statusFilter],
    queryFn: () => getVouchers(statusFilter ? { status: statusFilter } : undefined).then((r) => r.data),
  });

  const { data: plans } = useQuery({
    queryKey: ['plans-active'],
    queryFn: () => getPlans({ active_only: true }),
  });

  const { data: customersData } = useQuery({
    queryKey: ['customers-all'],
    queryFn: () => getCustomers({ page: 1, page_size: 200 }),
  });

  const generateMut = useMutation({
    mutationFn: generateVouchers,
    onSuccess: (res) => {
      const codes: VoucherType[] = res.data || [];
      setGeneratedCodes(codes.map((v) => v.code));
      message.success(`Generated ${codes.length} voucher(s)`);
      queryClient.invalidateQueries({ queryKey: ['vouchers'] });
    },
    onError: () => message.error('Failed to generate vouchers'),
  });

  const redeemMut = useMutation({
    mutationFn: redeemVoucher,
    onSuccess: () => {
      message.success('Voucher redeemed successfully');
      setRedeemOpen(false);
      redeemForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['vouchers'] });
    },
    onError: () => message.error('Failed to redeem voucher'),
  });

  const revokeMut = useMutation({
    mutationFn: revokeVoucher,
    onSuccess: () => {
      message.success('Voucher revoked');
      queryClient.invalidateQueries({ queryKey: ['vouchers'] });
    },
    onError: () => message.error('Failed to revoke voucher'),
  });

  const customers = customersData?.data?.items || [];

  const columns = [
    {
      title: 'Code',
      dataIndex: 'code',
      key: 'code',
      render: (code: string) => (
        <code style={{ fontFamily: 'monospace', fontSize: 13, color: '#e8700a' }}>{code}</code>
      ),
    },
    {
      title: 'Duration',
      dataIndex: 'duration_days',
      key: 'duration',
      render: (d: number) => `${d} days`,
      width: 100,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag color={STATUS_COLORS[s] || '#6b7280'}>{s}</Tag>,
      width: 100,
    },
    {
      title: 'Customer',
      dataIndex: 'customer_id',
      key: 'customer',
      render: (v: string | null) => v ? v.slice(0, 8) + '...' : '-',
      width: 120,
    },
    {
      title: 'Activated',
      dataIndex: 'activated_at',
      key: 'activated',
      render: (d: string | null) => d ? dayjs(d).format('YYYY-MM-DD') : '-',
      width: 110,
    },
    {
      title: 'Expires',
      dataIndex: 'expires_at',
      key: 'expires',
      render: (d: string | null) => d ? dayjs(d).format('YYYY-MM-DD') : '-',
      width: 110,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 80,
      render: (_: unknown, r: VoucherType) =>
        r.status === 'unused' ? (
          <Popconfirm title="Revoke this voucher?" onConfirm={() => revokeMut.mutate(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        ) : null,
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <TagsOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          Vouchers
        </Typography.Title>
        <Space>
          <Button icon={<GiftOutlined />} onClick={() => setRedeemOpen(true)}>
            Redeem
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setGeneratedCodes([]); setGenerateOpen(true); }}>
            Generate Vouchers
          </Button>
        </Space>
      </div>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="Filter by status"
            allowClear
            style={{ width: 160 }}
            value={statusFilter}
            onChange={setStatusFilter}
          >
            <Select.Option value="unused">Unused</Select.Option>
            <Select.Option value="active">Active</Select.Option>
            <Select.Option value="expired">Expired</Select.Option>
            <Select.Option value="revoked">Revoked</Select.Option>
          </Select>
        </Space>
        <Table
          dataSource={data || []}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ pageSize: 20, showTotal: (t) => `${t} vouchers` }}
        />
      </Card>

      {/* Generate Modal */}
      <Modal
        title="Generate Vouchers"
        open={generateOpen}
        onCancel={() => { setGenerateOpen(false); setGeneratedCodes([]); genForm.resetFields(); }}
        onOk={() => genForm.submit()}
        confirmLoading={generateMut.isPending}
        okText="Generate"
      >
        <Form
          form={genForm}
          layout="vertical"
          onFinish={(values) => generateMut.mutate(values)}
          initialValues={{ count: 10, duration_days: 30 }}
        >
          <Form.Item name="plan_id" label="Plan" rules={[{ required: true }]}>
            <Select placeholder="Select plan">
              {(plans?.data || []).map((p: any) => (
                <Select.Option key={p.id} value={p.id}>
                  {p.name} — ₱{p.monthly_price}/mo
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="duration_days" label="Duration (days)" rules={[{ required: true }]}>
            <InputNumber min={1} max={365} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="count" label="Count" rules={[{ required: true }]}>
            <InputNumber min={1} max={500} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
        {generatedCodes.length > 0 && (
          <Alert
            type="success"
            message={`Generated ${generatedCodes.length} codes`}
            description={
              <div style={{ maxHeight: 150, overflowY: 'auto', fontFamily: 'monospace', fontSize: 12 }}>
                {generatedCodes.map((c) => <div key={c}>{c}</div>)}
              </div>
            }
          />
        )}
      </Modal>

      {/* Redeem Modal */}
      <Modal
        title="Redeem Voucher"
        open={redeemOpen}
        onCancel={() => { setRedeemOpen(false); redeemForm.resetFields(); }}
        onOk={() => redeemForm.submit()}
        confirmLoading={redeemMut.isPending}
        okText="Redeem"
      >
        <Form form={redeemForm} layout="vertical" onFinish={(values) => redeemMut.mutate(values)}>
          <Form.Item name="code" label="Voucher Code" rules={[{ required: true }]}>
            <Input style={{ fontFamily: 'monospace', textTransform: 'uppercase' }} />
          </Form.Item>
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
                  {c.full_name} ({c.pppoe_username})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Vouchers;
