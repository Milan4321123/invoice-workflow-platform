"""
In-memory stand-in for the parts of the Supabase client the services use.

Used by the tests and by demo mode (DEMO_MODE=true), which lets someone run
the whole application without a Supabase project. Supports the query
builder calls the services make and a minimal file storage.
"""
import copy


class _Result:
    def __init__(self, data):
        self.data = data
        self.count = len(data)


class _Query:
    def __init__(self, table, op="select", payload=None):
        self.table, self.op, self.payload = table, op, payload
        self.filters, self.order_by, self.window = [], None, None
        self.columns = "*"

    # building
    def select(self, columns="*", count=None):
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append(lambda row: row.get(column) == value)
        return self

    def neq(self, column, value):
        self.filters.append(lambda row: row.get(column) != value)
        return self

    def ilike(self, column, pattern):
        # Only the exact-match use the services make: escaped _ and %, no wildcards
        wanted = pattern.replace("\\_", "_").replace("\\%", "%").replace("\\\\", "\\").lower()
        self.filters.append(lambda row: str(row.get(column) or "").lower() == wanted)
        return self

    def gte(self, column, value):
        self.filters.append(lambda row: row.get(column) is not None and row.get(column) >= value)
        return self

    def lt(self, column, value):
        self.filters.append(lambda row: row.get(column) is not None and row.get(column) < value)
        return self

    @property
    def not_(self):
        self._negate = True
        return self

    def is_(self, column, value):
        check = (lambda row: row.get(column) is None) if value == "null" else (lambda row: row.get(column) == value)
        if getattr(self, "_negate", False):
            self._negate = False
            self.filters.append(lambda row: not check(row))
        else:
            self.filters.append(check)
        return self

    def in_(self, column, values):
        values = set(values)
        self.filters.append(lambda row: row.get(column) in values)
        return self

    def order(self, column, desc=False):
        self.order_by = (column, desc)
        return self

    def limit(self, n):
        self.window = (0, n - 1)
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    # running
    def _matching(self):
        rows = [row for row in self.table.rows if all(f(row) for f in self.filters)]
        if self.order_by:
            column, desc = self.order_by
            rows.sort(key=lambda row: row.get(column), reverse=desc)
        if self.window:
            rows = rows[self.window[0]:self.window[1] + 1]
        return rows

    def execute(self):
        if self.op == "insert":
            row = copy.deepcopy(self.payload)
            for column in self.table.unique:
                if any(existing.get(column) == row.get(column) for existing in self.table.rows):
                    raise Exception(f'duplicate key value violates unique constraint "{column}" (23505)')
            self.table.rows.append(row)
            return _Result([copy.deepcopy(row)])
        matching = self._matching()
        if self.op == "update":
            for row in matching:
                row.update(copy.deepcopy(self.payload))
        elif self.op == "delete":
            if self.table.append_only:
                raise Exception("append-only")
            self.table.rows = [row for row in self.table.rows if row not in matching]
        if self.op == "select" and self.columns != "*":
            wanted = [c.strip() for c in self.columns.split(",")]
            return _Result([{c: copy.deepcopy(row.get(c)) for c in wanted} for row in matching])
        return _Result([copy.deepcopy(row) for row in matching])


class FakeTable:
    def __init__(self, rows=None, unique=(), append_only=False):
        self.rows = rows or []
        self.unique = unique
        self.append_only = append_only

    def select(self, *args, **kwargs):
        return _Query(self).select(*args, **kwargs)

    def insert(self, payload):
        return _Query(self, "insert", payload)

    def update(self, payload):
        return _Query(self, "update", payload)

    def delete(self):
        return _Query(self, "delete")


class _Bucket:
    def __init__(self, files):
        self.files = files

    def upload(self, name, content, *args, **kwargs):
        self.files[name] = bytes(content)
        return {"Key": name}

    def download(self, name):
        return self.files[name]

    def remove(self, names):
        for name in names:
            self.files.pop(name, None)
        return names

    def get_public_url(self, name):
        return name

    def create_signed_url(self, name, expires_in):
        return {"signedURL": name}


class _Storage:
    def __init__(self):
        self.buckets = {}

    def from_(self, bucket):
        return _Bucket(self.buckets.setdefault(bucket, {}))


class FakeSupabase:
    def __init__(self, **tables):
        self.tables = tables
        self.storage = _Storage()

    def table(self, name):
        return self.tables.setdefault(name, FakeTable())
