export interface Resource {
  id: string;
  title: string;
  tags: string[];
  rank: number;
}

export interface Catalog {
  resources: Resource[];
}
