import type { WorkOrderStatus, WorkOrder } from "./types.ts";

export interface ListQuery {
  status?: WorkOrderStatus;
  sort: "createdAt" | "title" | "id";
  order: "asc" | "desc";
  page: number;
  pageSize: number;
}

export interface ListPage {
  total: number;
  page: number;
  pageSize: number;
  pages: number;
  items: WorkOrder[];
}
