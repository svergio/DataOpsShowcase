type ModelFiltersProps = {
  tags: string;
  resourceType: string;
  schema: string;
  packageName: string;
  onChange: (patch: Partial<ModelFiltersProps>) => void;
};

export function ModelFilters(props: ModelFiltersProps) {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <input placeholder="tags" value={props.tags} onChange={(e) => props.onChange({ tags: e.target.value })} />
      <input
        placeholder="resource_type"
        value={props.resourceType}
        onChange={(e) => props.onChange({ resourceType: e.target.value })}
      />
      <input placeholder="schema" value={props.schema} onChange={(e) => props.onChange({ schema: e.target.value })} />
      <input
        placeholder="package_name"
        value={props.packageName}
        onChange={(e) => props.onChange({ packageName: e.target.value })}
      />
    </div>
  );
}
