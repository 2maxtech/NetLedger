import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Card, Typography, Select, Space, Button, message, DatePicker, Popconfirm } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import StatusTag from '../../components/StatusTag';
import { getInvoices, generateInvoices, updateInvoice } from '../../api/billing';
import type { Invoice } from '../../api/billing';

const Invoices = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['invoices', page, statusFilter, dateRange],
    queryFn: () =>
      getInvoices({
        page,
        size: 20,
        status: statusFilter,
        from_date: dateRange?.[0]?.format('YYYY-MM-DD'),
        to_date: dateRange?.[1]?.format('YYYY-MM-DD'),
      }).then((r) => r.data),
  });

  const generateMut = useMutation({
    mutationFn: () => generateInvoices(),
    onSuccess: (res) => {
      message.success(`Generated ${res.data.generated} invoice(s), skipped ${res.data.skipped}`);
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    onError: () => message.error('Failed to generate invoices'),
  });

  const voidMut = useMutation({
    mutationFn: (id: string) => updateInvoice(id, { status: 'void' }),
    onSuccess: () => {
      message.success('Invoice voided');
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    onError: () => message.error('Failed to void invoice'),
  });

  const columns = [
    {
      title: 'Customer',
      dataIndex: 'customer_name',
      key: 'customer',
      ellipsis: true,
    },
    {
      title: 'Amount',
      key: 'amount',
      render: (_: unknown, r: Invoice) => `₱${Number(r.amount).toLocaleString('en-PH', { minimumFractionDigits: 2 })}`,
      width: 120,
    },
    {
      title: 'Paid',
      key: 'total_paid',
      render: (_: unknown, r: Invoice) => r.total_paid ? `₱${Number(r.total_paid).toLocaleString('en-PH', { minimumFractionDigits: 2 })}` : '₱0.00',
      width: 120,
    },
    {
      title: 'Due Date',
      dataIndex: 'due_date',
      key: 'due',
      width: 110,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <StatusTag status={s} />,
      width: 100,
    },
    {
      title: 'Issued',
      dataIndex: 'issued_at',
      key: 'issued',
      render: (d: string) => dayjs(d).format('YYYY-MM-DD'),
      width: 110,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 80,
      render: (_: unknown, r: Invoice) =>
        r.status !== 'void' && r.status !== 'paid' ? (
          <Popconfirm title="Void this invoice?" onConfirm={() => voidMut.mutate(r.id)}>
            <Button type="link" size="small" danger>Void</Button>
          </Popconfirm>
        ) : null,
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>Invoices</Typography.Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          loading={generateMut.isPending}
          onClick={() => generateMut.mutate()}
        >
          Generate Invoices
        </Button>
      </div>
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            placeholder="Filter by status"
            allowClear
            style={{ width: 150 }}
            value={statusFilter}
            onChange={setStatusFilter}
          >
            <Select.Option value="pending">Pending</Select.Option>
            <Select.Option value="paid">Paid</Select.Option>
            <Select.Option value="overdue">Overdue</Select.Option>
            <Select.Option value="void">Void</Select.Option>
          </Select>
          <DatePicker.RangePicker
            onChange={(dates) => setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={() => queryClient.invalidateQueries({ queryKey: ['invoices'] })}
          />
        </Space>
        <Table
          columns={columns}
          dataSource={data?.items || []}
          rowKey="id"
          loading={isLoading}
          pagination={{
            current: page,
            pageSize: 20,
            total: data?.total || 0,
            onChange: setPage,
            showTotal: (total) => `${total} invoices`,
          }}
        />
      </Card>
    </div>
  );
};

export default Invoices;
