import { Card, Statistic } from 'antd';
import type { ReactNode } from 'react';

interface StatCardProps {
  title: string;
  value: number | string;
  prefix?: ReactNode;
  valueStyle?: React.CSSProperties;
}

const StatCard = ({ title, value, prefix, valueStyle }: StatCardProps) => (
  <Card>
    <Statistic title={title} value={value} prefix={prefix} valueStyle={valueStyle} />
  </Card>
);

export default StatCard;
