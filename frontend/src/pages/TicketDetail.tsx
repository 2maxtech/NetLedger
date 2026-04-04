import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Button, Typography, Space, Tag, Select, Input, Spin, Empty, message,
} from 'antd';
import { ArrowLeftOutlined, SendOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { getTicket, updateTicket, addTicketMessage, type TicketMessage } from '../api/tickets';

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

const TicketDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [replyText, setReplyText] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['ticket', id],
    queryFn: () => getTicket(id!).then((r) => r.data),
    enabled: !!id,
  });

  const updateMut = useMutation({
    mutationFn: (payload: any) => updateTicket(id!, payload),
    onSuccess: () => {
      message.success('Ticket updated');
      queryClient.invalidateQueries({ queryKey: ['ticket', id] });
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
    },
    onError: () => message.error('Failed to update ticket'),
  });

  const replyMut = useMutation({
    mutationFn: (text: string) => addTicketMessage(id!, { message: text, sender_type: 'staff' }),
    onSuccess: () => {
      setReplyText('');
      queryClient.invalidateQueries({ queryKey: ['ticket', id] });
    },
    onError: () => message.error('Failed to send reply'),
  });

  if (isLoading) return <Spin size="large" />;
  if (!data) return <Empty description="Ticket not found" />;

  const ticket = data;

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tickets')}>
          Back
        </Button>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>{ticket.subject}</Typography.Title>
            <Space style={{ marginTop: 8 }}>
              <Tag color={STATUS_COLORS[ticket.status] || '#6b7280'}>
                {ticket.status.replace('_', ' ')}
              </Tag>
              <Tag color={PRIORITY_COLORS[ticket.priority] || '#6b7280'}>
                {ticket.priority}
              </Tag>
              <Typography.Text type="secondary">
                Opened {dayjs(ticket.created_at).format('YYYY-MM-DD HH:mm')}
              </Typography.Text>
            </Space>
          </div>
          <Space wrap>
            <Select
              value={ticket.status}
              style={{ width: 140 }}
              onChange={(val) => updateMut.mutate({ status: val })}
            >
              <Select.Option value="open">Open</Select.Option>
              <Select.Option value="in_progress">In Progress</Select.Option>
              <Select.Option value="resolved">Resolved</Select.Option>
              <Select.Option value="closed">Closed</Select.Option>
            </Select>
            <Select
              value={ticket.assigned_to || undefined}
              placeholder="Assign to..."
              style={{ width: 160 }}
              allowClear
              onChange={(val) => updateMut.mutate({ assigned_to: val || null })}
            >
              <Select.Option value="admin">Admin</Select.Option>
              <Select.Option value="support">Support</Select.Option>
              <Select.Option value="technician">Technician</Select.Option>
            </Select>
          </Space>
        </div>
      </Card>

      {/* Message thread */}
      <Card title="Messages" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {(ticket.messages || []).length === 0 && (
            <Typography.Text type="secondary">No messages yet.</Typography.Text>
          )}
          {(ticket.messages || []).map((msg: TicketMessage) => {
            const isStaff = msg.sender_type === 'staff';
            return (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  justifyContent: isStaff ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    maxWidth: '70%',
                    background: isStaff ? '#e8700a' : '#f1f5f9',
                    color: isStaff ? '#fff' : '#1e293b',
                    borderRadius: 12,
                    padding: '10px 14px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4, opacity: 0.85 }}>
                    {isStaff ? 'Staff' : 'Customer'}
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap' }}>{msg.message}</div>
                  <div
                    style={{
                      fontSize: 11,
                      marginTop: 6,
                      opacity: 0.7,
                      textAlign: 'right',
                    }}
                  >
                    {dayjs(msg.created_at).format('MMM D, HH:mm')}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Reply */}
      <Card>
        <Space.Compact style={{ width: '100%' }}>
          <Input.TextArea
            rows={3}
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder="Type your reply..."
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.ctrlKey && replyText.trim()) {
                replyMut.mutate(replyText.trim());
              }
            }}
          />
        </Space.Compact>
        <div style={{ textAlign: 'right', marginTop: 8 }}>
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={replyMut.isPending}
            disabled={!replyText.trim()}
            onClick={() => replyMut.mutate(replyText.trim())}
          >
            Send Reply
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default TicketDetail;
