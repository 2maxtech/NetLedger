import { useState } from 'react';
import {
  Table, Card, Button, Modal, Form, Input, InputNumber, Select, DatePicker,
  Typography, Popconfirm, Space, message, Tag, Row, Col, Statistic,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import {
  getExpenses, createExpense, updateExpense, deleteExpense, getExpenseSummary,
  type ExpenseType,
} from '../api/expenses';

const CATEGORY_COLORS: Record<string, string> = {
  equipment: '#3b82f6',
  electricity: '#f59e0b',
  rent: '#8b5cf6',
  salary: '#10b981',
  maintenance: '#e8700a',
  internet: '#06b6d4',
  other: '#6b7280',
};

const CATEGORIES = ['equipment', 'electricity', 'rent', 'salary', 'maintenance', 'internet', 'other'];

const Expenses = () => {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingExpense, setEditingExpense] = useState<ExpenseType | null>(null);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [form] = Form.useForm();

  const rangeParams = dateRange
    ? { from_date: dateRange[0]?.format('YYYY-MM-DD'), to_date: dateRange[1]?.format('YYYY-MM-DD') }
    : {};

  const { data, isLoading } = useQuery({
    queryKey: ['expenses', dateRange],
    queryFn: () => getExpenses(rangeParams).then((r) => r.data),
  });

  const { data: summary } = useQuery({
    queryKey: ['expense-summary', dateRange],
    queryFn: () => getExpenseSummary(rangeParams).then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: createExpense,
    onSuccess: () => {
      message.success('Expense recorded');
      closeModal();
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['expense-summary'] });
    },
    onError: () => message.error('Failed to record expense'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateExpense(id, data),
    onSuccess: () => {
      message.success('Expense updated');
      closeModal();
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['expense-summary'] });
    },
    onError: () => message.error('Failed to update expense'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteExpense,
    onSuccess: () => {
      message.success('Expense deleted');
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['expense-summary'] });
    },
    onError: () => message.error('Failed to delete expense'),
  });

  const closeModal = () => {
    setModalOpen(false);
    setEditingExpense(null);
    form.resetFields();
  };

  const openEdit = (expense: ExpenseType) => {
    setEditingExpense(expense);
    form.setFieldsValue({
      category: expense.category,
      description: expense.description,
      amount: parseFloat(expense.amount),
      date: dayjs(expense.date),
      receipt_number: expense.receipt_number,
    });
    setModalOpen(true);
  };

  const onFinish = (values: any) => {
    const payload = { ...values, date: values.date?.format('YYYY-MM-DD') };
    if (editingExpense) updateMut.mutate({ id: editingExpense.id, data: payload });
    else createMut.mutate(payload);
  };

  const formatAmount = (v: string | number) =>
    `₱${Number(v).toLocaleString('en-PH', { minimumFractionDigits: 2 })}`;

  const columns = [
    {
      title: 'Date',
      dataIndex: 'date',
      key: 'date',
      width: 110,
      render: (d: string) => dayjs(d).format('YYYY-MM-DD'),
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      render: (c: string) => (
        <Tag color={CATEGORY_COLORS[c] || '#6b7280'}>{c}</Tag>
      ),
      width: 120,
    },
    { title: 'Description', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: 'Amount',
      dataIndex: 'amount',
      key: 'amount',
      render: (v: string) => formatAmount(v),
      width: 130,
    },
    {
      title: 'Receipt #',
      dataIndex: 'receipt_number',
      key: 'receipt',
      render: (v: string | null) => v || '-',
      width: 110,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 90,
      render: (_: unknown, record: ExpenseType) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="Delete this expense?" onConfirm={() => deleteMut.mutate(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const totalMonth = summary?.total_this_month ?? 0;
  const byCategory: Record<string, number> = summary?.by_category ?? {};

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>Expenses</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          Add Expense
        </Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="This Month Total"
              value={totalMonth}
              prefix="₱"
              precision={2}
              valueStyle={{ color: '#e8700a' }}
            />
          </Card>
        </Col>
        {Object.entries(byCategory).map(([cat, amt]) => (
          <Col xs={24} sm={8} key={cat}>
            <Card>
              <Statistic
                title={cat.charAt(0).toUpperCase() + cat.slice(1)}
                value={amt}
                prefix="₱"
                precision={2}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <DatePicker.RangePicker
            onChange={(dates) =>
              setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)
            }
          />
        </Space>
        <Table
          dataSource={data?.items || []}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ total: data?.total || 0, pageSize: 20, showTotal: (t) => `${t} expenses` }}
        />
      </Card>

      <Modal
        title={editingExpense ? 'Edit Expense' : 'Add Expense'}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={createMut.isPending || updateMut.isPending}
      >
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="category" label="Category" rules={[{ required: true }]}>
            <Select>
              {CATEGORIES.map((c) => (
                <Select.Option key={c} value={c}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="description" label="Description" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="amount" label="Amount (₱)" rules={[{ required: true }]}>
            <InputNumber min={0} precision={2} style={{ width: '100%' }} prefix="₱" />
          </Form.Item>
          <Form.Item name="date" label="Date" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="receipt_number" label="Receipt Number">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Expenses;
