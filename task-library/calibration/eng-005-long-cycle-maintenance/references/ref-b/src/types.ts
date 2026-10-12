export type WorkOrderStatus = "OPEN" | "IN_PROGRESS" | "DONE";

export interface WorkOrder {
  id: string;
  title: string;
  status: WorkOrderStatus;
  createdAt: string;
  description: string;
  dependsOn?: string[];
}

export interface WorkOrderEvent {
  sequence: number;
  type: string;
  orderId: string | null;
  at: string;
}

export interface StoreV1 {
  version: 1;
  workOrders: WorkOrder[];
}

export interface StoreV2 {
  version: 2;
  workOrders: WorkOrder[];
  events: WorkOrderEvent[];
}

export type Store = StoreV1 | StoreV2;
