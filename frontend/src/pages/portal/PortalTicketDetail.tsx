import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Card, Typography, Button, Space, Tag, Input, Spin, Empty, message,
} from 'antd';
import { ArrowLeftOutlined, SendOutlined } from '@ant-design/icons';
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

const PortalTicketDetail = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [replyText, setReplyText] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['portal-ticket', id],
    queryFn: () => portalClient.get(`/tickets/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const replyMut = useMutation({
    mutationFn: (text: string) =>
      portalClient.post(`/tickets/${id}/messages`, { message: text, sender_type: 'customer' }),
    onSuccess: () => {
      setReplyText('');
      queryClient.invalidateQueries({ queryKey: ['portal-ticket', id] });
    },
    onError: () => message.error('Failed to send reply'),
  });

  if (isLoading) return <Spin size="large" />;
  if (!data) return <Empty description="Ticket not found" />;

  const ticket = data;

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Link to="/portal/tickets">
          <ArrowLeftOutlined /> Back to Tickets
        </Link>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {ticket.subject}
        </Typography.Title>
        <Space style={{ marginTop: 8 }}>
          <Tag color={STATUS_COLORS[ticket.status] || '#6b7280'}>
            {ticket.status?.replace('_', ' ')}
          </Tag>
          <Typography.Text type="secondary">
            Opened {dayjs(ticket.created_at).format('YYYY-MM-DD HH:mm')}
          </Typography.Text>
        </Space>
      </Card>

      <Card title="Messages" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {(ticket.messages || []).length === 0 && (
            <Typography.Text type="secondary">No messages yet.</Typography.Text>
          )}
          {(ticket.messages || []).map((msg: any) => {
            const isStaff = msg.sender_type === 'staff';
            return (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  justifyContent: isStaff ? 'flex-start' : 'flex-end',
                }}
              >
                <div
                  style={{
                    maxWidth: '70%',
                    background: isStaff ? '#f1f5f9' : '#e8700a',
                    color: isStaff ? '#1e293b' : '#fff',
                    borderRadius: 12,
                    padding: '10px 14px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4, opacity: 0.85 }}>
                    {isStaff ? 'Support' : 'You'}
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap' }}>{msg.message}</div>
                  <div style={{ fontSize: 11, marginTop: 6, opacity: 0.7, textAlign: 'right' }}>
                    {dayjs(msg.created_at).format('MMM D, HH:mm')}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {ticket.status !== 'closed' && ticket.status !== 'resolved' && (
        <Card>
          <Input.TextArea
            rows={3}
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder="Type your reply..."
          />
          <div style={{ textAlign: 'right', marginTop: 8 }}>
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={replyMut.isPending}
              disabled={!replyText.trim()}
              onClick={() => replyMut.mutate(replyText.trim())}
            >
              Send
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
};

export default PortalTicketDetail;
