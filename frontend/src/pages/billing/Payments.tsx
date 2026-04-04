import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Card, Typography, Button, Modal, Form, Input, Select, InputNumber, message, Space, DatePicker } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getPayments, recordPayment } from '../../api/billing';
import { getInvoices } from '../../api/billing';
import type { Payment, Invoice } from '../../api/billing';

const Payments = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['payments', page, dateRange],
    queryFn: () =>
      getPayments({
        page,
        size: 20,
        from_date: dateRange?.[0]?.format('YYYY-MM-DD'),
        to_date: dateRange?.[1]?.format('YYYY-MM-DD'),
      }).then((r) => r.data),
  });

  // Fetch unpaid invoices for the payment modal
  const { data: unpaidInvoices } = useQuery({
    queryKey: ['invoices-unpaid'],
    queryFn: () =>
      getInvoices({ size: 100, status: 'pending' })
        .then((r) => r.data.items)
        .then(async (pending) => {
          const overdueResp = await getInvoices({ size: 100, status: 'overdue' });
          return [...pending, ...overdueResp.data.items];
        }),
    enabled: modalOpen,
  });

  const payMut = useMutation({
    mutationFn: recordPayment,
    onSuccess: () => {
      message.success('Payment recorded');
      setModalOpen(false);
      form.resetFields();
      setSelectedInvoice(null);
      queryClient.invalidateQueries({ queryKey: ['payments'] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    onError: () => message.error('Failed to record payment'),
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
      render: (_: unknown, r: Payment) => `₱${Number(r.amount).toLocaleString('en-PH', { minimumFractionDigits: 2 })}`,
      width: 120,
    },
    {
      title: 'Method',
      dataIndex: 'method',
      key: 'method',
      render: (m: string) => m.charAt(0).toUpperCase() + m.slice(1),
      width: 90,
    },
    {
      title: 'Reference',
      dataIndex: 'reference_number',
      key: 'ref',
      render: (r: string | null) => r || '-',
      width: 140,
    },
    {
      title: 'Invoice Amount',
      key: 'invoice_amount',
      render: (_: unknown, r: Payment) => r.invoice_amount ? `₱${Number(r.invoice_amount).toLocaleString('en-PH', { minimumFractionDigits: 2 })}` : '-',
      width: 130,
    },
    {
      title: 'Date',
      dataIndex: 'received_at',
      key: 'date',
      render: (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm'),
      width: 150,
    },
  ];

  const handleInvoiceSelect = (invoiceId: string) => {
    const inv = unpaidInvoices?.find((i) => i.id === invoiceId) || null;
    setSelectedInvoice(inv);
    if (inv) {
      const paid = Number(inv.total_paid || 0);
      const remaining = Number(inv.amount) - paid;
      form.setFieldsValue({ amount: remaining > 0 ? remaining : Number(inv.amount) });
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>Payments</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          Record Payment
        </Button>
      </div>
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <DatePicker.RangePicker
            onChange={(dates) => setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={() => queryClient.invalidateQueries({ queryKey: ['payments'] })}
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
            showTotal: (total) => `${total} payments`,
          }}
        />
      </Card>

      <Modal
        title="Record Payment"
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields(); setSelectedInvoice(null); }}
        onOk={() => form.submit()}
        confirmLoading={payMut.isPending}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) =>
            payMut.mutate({
              invoice_id: values.invoice_id,
              amount: String(values.amount),
              method: values.method,
              reference_number: values.reference_number || undefined,
            })
          }
        >
          <Form.Item name="invoice_id" label="Invoice" rules={[{ required: true, message: 'Select an invoice' }]}>
            <Select
              showSearch
              placeholder="Search by customer name"
              optionFilterProp="label"
              onChange={handleInvoiceSelect}
              options={(unpaidInvoices || []).map((inv) => ({
                value: inv.id,
                label: `${inv.customer_name} - ₱${Number(inv.amount).toFixed(2)} (due ${inv.due_date})`,
              }))}
            />
          </Form.Item>
          {selectedInvoice && (
            <div style={{ marginBottom: 16, padding: 8, background: '#f5f5f5', borderRadius: 4, fontSize: 13 }}>
              Invoice: ₱{Number(selectedInvoice.amount).toFixed(2)} | Paid: ₱{Number(selectedInvoice.total_paid || 0).toFixed(2)} | Remaining: ₱{(Number(selectedInvoice.amount) - Number(selectedInvoice.total_paid || 0)).toFixed(2)}
            </div>
          )}
          <Form.Item name="amount" label="Amount" rules={[{ required: true, message: 'Enter amount' }]}>
            <InputNumber style={{ width: '100%' }} min={0.01} precision={2} prefix="₱" />
          </Form.Item>
          <Form.Item name="method" label="Payment Method" rules={[{ required: true, message: 'Select method' }]}>
            <Select>
              <Select.Option value="cash">Cash</Select.Option>
              <Select.Option value="bank">Bank Transfer</Select.Option>
              <Select.Option value="online">Online</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="reference_number" label="Reference Number">
            <Input placeholder="Bank ref, receipt #, etc." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Payments;
