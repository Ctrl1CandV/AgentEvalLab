"""Hidden tests for the query item: queries over two small tables and the full expected results, written by hand.

Fixtures are grouped into checks, one per rule area. A check passes when every fixture in it produces exactly the
expected output.
"""

TABLES = {
    "people": {"columns": ["id", "name", "city", "age", "score"],
               "rows": [[1, "Ada", "Oslo", 36, 9.5], [2, "bob", "Lima", None, 7.25], [3, "Cy", "Oslo", 41, None], [4, "Dee", None, 29, 8],
                        [5, "Eve", "Lima", 36, 7.25]]},
    "orders": {"columns": ["oid", "pid", "amount", "status"],
               "rows": [[10, 1, 20, "paid"], [11, 1, 5.5, "open"], [12, 3, 12, "paid"], [13, 9, 7, "paid"], [14, 4, None, "void"]]},
}


def res(columns, rows):
    return {"columns": columns, "rows": rows}


def err(code):
    return {"error": code}


def cols(count):
    return [f"col{index}" for index in range(1, count + 1)]


def fixture(check, name, pairs):
    """pairs: [(query, expected result)]."""
    return (check, name, {"tables": TABLES, "queries": [query for query, _ in pairs]}, {"results": [result for _, result in pairs]})


FIXTURES = [
    fixture("basics", "select-where-limit", [
        ("SELECT name, age FROM people WHERE age > 30", res(["name", "age"], [["Ada", 36], ["Cy", 41], ["Eve", 36]])),
        ("select id, name from People p where P.CITY = 'Oslo'", res(["id", "name"], [[1, "Ada"], [3, "Cy"]])),
        ("SELECT * FROM orders LIMIT 2 OFFSET 1", res(["oid", "pid", "amount", "status"], [[11, 1, 5.5, "open"], [12, 3, 12, "paid"]])),
        ("SELECT name AS who, age + 1, 'x' FROM people WHERE id = 4", res(["who", "col2", "col3"], [["Dee", 30, "x"]])),
    ]),
    fixture("arithmetic", "exact-numbers", [
        ("SELECT 7 / 2, 6 / 3, -7 % 3, 7 % -3, 0.1 + 0.2, 2 * 1.5 FROM people WHERE id = 1", res(cols(6), [[3.5, 2, -1, 1, 0.3, 3]])),
        ("SELECT 1 / 3, 2.5 % 2 FROM people WHERE id = 1", err("TYPE_MISMATCH")),
        ("SELECT 1 / 3, 10 / 4.0 FROM people WHERE id = 1", res(cols(2), [[0.333333, 2.5]])),
        ("SELECT score * 2, age - score FROM people", res(cols(2), [[19, 26.5], [14.5, None], [None, None], [16, 21], [14.5, 28.75]])),
        ("SELECT 2 / 3, 1.0000005 * 1 FROM people WHERE id = 1", res(cols(2), [[0.666667, 1]])),
    ]),
    fixture("division", "zero-and-null", [
        ("SELECT 1 / 0 FROM people WHERE id = 1", err("DIVISION_BY_ZERO")),
        ("SELECT 5 % 0 FROM people WHERE id = 1", err("DIVISION_BY_ZERO")),
        ("SELECT NULL / 0 FROM people WHERE id = 1", res(cols(1), [[None]])),
        ("SELECT id FROM people WHERE id > 10 AND 1 / 0 = 1", res(["id"], [])),
        ("SELECT 1 / (age - 36) FROM people WHERE age <> 36", res(cols(1), [[0.2], [-0.142857]])),
    ]),
    fixture("types", "kinds-and-text", [
        ("SELECT id FROM people WHERE name > 5", err("TYPE_MISMATCH")),
        ("SELECT id FROM people WHERE city = NULL", res(["id"], [])),
        ("SELECT TRUE < FALSE, 1 = 1.0, 'a' < 'B', 'B' < 'a' FROM people WHERE id = 1", res(cols(4), [[False, True, False, True]])),
        ("SELECT 1 + TRUE FROM people WHERE id = 1", err("TYPE_MISMATCH")),
        ("SELECT NULL + 'x', name || age, 2.50 || '', TRUE || NULL FROM people WHERE id = 1", res(cols(4), [[None, "Ada36", "2.5", None]])),
        ("SELECT id FROM people WHERE age AND TRUE", err("TYPE_MISMATCH")),
    ]),
    fixture("logic", "three-valued", [
        ("SELECT id, age > 30 OR city = 'Lima', NOT (age > 30) FROM people",
         res(["id", "col2", "col3"], [[1, True, False], [2, True, None], [3, True, False], [4, None, True], [5, True, False]])),
        ("SELECT id FROM people WHERE age IN (29, 41, NULL)", res(["id"], [[3], [4]])),
        ("SELECT id FROM people WHERE age NOT IN (29, 41)", res(["id"], [[1], [5]])),
        ("SELECT id FROM people WHERE score BETWEEN 7.25 AND 9", res(["id"], [[2], [4], [5]])),
        ("SELECT id FROM people WHERE age NOT BETWEEN 30 AND 40", res(["id"], [[3], [4]])),
        ("SELECT 1 IN (2, 'x') FROM people WHERE id = 1", err("TYPE_MISMATCH")),
        ("SELECT 1 IN (1, 'x') FROM people WHERE id = 1", res(cols(1), [[True]])),
        ("SELECT id, age IN (29, NULL), age NOT IN (41) FROM people",
         res(["id", "col2", "col3"], [[1, None, True], [2, None, None], [3, None, False], [4, True, True], [5, None, True]])),
    ]),
    fixture("like-functions", "patterns-and-functions", [
        ("SELECT name FROM people WHERE name LIKE '_o%'", res(["name"], [["bob"]])),
        ("SELECT name FROM people WHERE name LIKE 'B%'", res(["name"], [])),
        ("SELECT UPPER(name), LOWER(city), LENGTH(name), ABS(-2.5), ROUND(2.345, 2), ROUND(-2.5, 0), ROUND(7, 2) FROM people WHERE id = 4",
         res(cols(7), [["DEE", None, 3, 2.5, 2.35, -3, 7]])),
        ("SELECT COALESCE(city, 'none'), COALESCE(NULL, NULL) FROM people WHERE id = 4", res(cols(2), [["none", None]])),
        ("SELECT LENGTH(age) FROM people WHERE id = 1", err("TYPE_MISMATCH")),
        ("SELECT CASE WHEN age > 35 THEN 'senior' WHEN age > 30 THEN 'mid' ELSE 'young' END AS band FROM people",
         res(["band"], [["senior"], ["young"], ["senior"], ["young"], ["senior"]])),
        ("SELECT CASE WHEN id = 1 THEN 1 ELSE 1 / 0 END FROM people WHERE id = 1", res(cols(1), [[1]])),
    ]),
    fixture("aggregates", "aggregate-functions", [
        ("SELECT COUNT(*), COUNT(age), SUM(age), AVG(age), MIN(name), MAX(score) FROM people", res(cols(6), [[5, 4, 142, 35.5, "Ada", 9.5]])),
        ("SELECT COUNT(*), SUM(age), AVG(score) FROM people WHERE age > 100", res(cols(3), [[0, None, None]])),
        ("SELECT SUM(score), AVG(score), COUNT(DISTINCT score), SUM(DISTINCT score) FROM people", res(cols(4), [[32, 8, 3, 24.75]])),
        ("SELECT AVG(age) FROM people WHERE city = 'Lima'", res(cols(1), [[36]])),
        ("SELECT MAX(city || age) FROM people", res(cols(1), [["Oslo41"]])),
        ("SELECT MIN(age), MAX(name) FROM people WHERE id = 99", res(cols(2), [[None, None]])),
    ]),
    fixture("grouping", "groups-and-having", [
        ("SELECT city, COUNT(*) AS n, SUM(age) FROM people GROUP BY city", res(["city", "n", "col3"], [["Oslo", 2, 77], ["Lima", 2, 36], [None, 1, 29]])),
        ("SELECT city, COUNT(*) FROM people GROUP BY city HAVING COUNT(*) > 1", res(["city", "col2"], [["Oslo", 2], ["Lima", 2]])),
        ("SELECT name, COUNT(*) FROM people GROUP BY city", err("GROUPING_ERROR")),
        ("SELECT city FROM people WHERE COUNT(*) > 1 GROUP BY city", err("GROUPING_ERROR")),
        ("SELECT age, COUNT(*) FROM people GROUP BY age ORDER BY age", res(["age", "col2"], [[29, 1], [36, 2], [41, 1], [None, 1]])),
        ("SELECT COUNT(*) FROM people HAVING id > 1", err("GROUPING_ERROR")),
        ("SELECT id FROM people HAVING id > 1", err("GROUPING_ERROR")),
        ("SELECT SUM(MAX(age)) FROM people", err("GROUPING_ERROR")),
        ("SELECT score, COUNT(*) FROM people GROUP BY score", res(["score", "col2"], [[9.5, 1], [7.25, 2], [None, 1], [8, 1]])),
    ]),
    fixture("ordering", "order-distinct-limit", [
        ("SELECT name, age FROM people ORDER BY age DESC, name", res(["name", "age"], [["bob", None], ["Cy", 41], ["Ada", 36], ["Eve", 36], ["Dee", 29]])),
        ("SELECT name AS n, city FROM people ORDER BY city, n DESC",
         res(["n", "city"], [["bob", "Lima"], ["Eve", "Lima"], ["Cy", "Oslo"], ["Ada", "Oslo"], ["Dee", None]])),
        ("SELECT name, score FROM people ORDER BY 2, 1", res(["name", "score"], [["Eve", 7.25], ["bob", 7.25], ["Dee", 8], ["Ada", 9.5], ["Cy", None]])),
        ("SELECT name FROM people ORDER BY 3", err("PARSE_ERROR")),
        ("SELECT name, city FROM people ORDER BY CASE WHEN city IS NULL THEN 0 ELSE 1 END, id DESC",
         res(["name", "city"], [["Dee", None], ["Eve", "Lima"], ["Cy", "Oslo"], ["bob", "Lima"], ["Ada", "Oslo"]])),
        ("SELECT id FROM people ORDER BY CASE WHEN id = 1 THEN 'a' ELSE 1 END", err("TYPE_MISMATCH")),
        ("SELECT DISTINCT city FROM people ORDER BY city LIMIT 2", res(["city"], [["Lima"], ["Oslo"]])),
        ("SELECT DISTINCT score FROM people", res(["score"], [[9.5], [7.25], [None], [8]])),
    ]),
    fixture("joins", "inner-and-left", [
        ("SELECT p.name, o.amount FROM people p JOIN orders o ON o.pid = p.id ORDER BY o.oid",
         res(["name", "amount"], [["Ada", 20], ["Ada", 5.5], ["Cy", 12], ["Dee", None]])),
        ("SELECT p.name, o.oid FROM people p LEFT JOIN orders o ON o.pid = p.id AND o.status = 'paid'",
         res(["name", "oid"], [["Ada", 10], ["bob", None], ["Cy", 12], ["Dee", None], ["Eve", None]])),
        ("SELECT name, status FROM people JOIN orders ON pid = id WHERE status = 'paid'", res(["name", "status"], [["Ada", "paid"], ["Cy", "paid"]])),
        ("SELECT * FROM people p JOIN orders o ON o.pid = p.id WHERE o.oid = 12",
         res(["id", "name", "city", "age", "score", "oid", "pid", "amount", "status"], [[3, "Cy", "Oslo", 41, None, 12, 3, 12, "paid"]])),
        ("SELECT p.name, COUNT(o.oid), SUM(o.amount) FROM people p LEFT JOIN orders o ON o.pid = p.id GROUP BY p.name ORDER BY p.name",
         res(["name", "col2", "col3"], [["Ada", 2, 25.5], ["Cy", 1, 12], ["Dee", 1, None], ["Eve", 0, None], ["bob", 0, None]])),
    ]),
    fixture("names", "name-errors-and-aliases", [
        ("SELECT id FROM persons", err("UNKNOWN_TABLE")),
        ("SELECT nme FROM people", err("UNKNOWN_COLUMN")),
        ("SELECT id FROM people a JOIN people b ON a.id = b.id", err("AMBIGUOUS_COLUMN")),
        ("SELECT people.name FROM people p", err("UNKNOWN_COLUMN")),
        ("SELECT nme FROM persons", err("UNKNOWN_TABLE")),
        ("SELECT CASE WHEN FALSE THEN missing ELSE 1 END FROM people", err("UNKNOWN_COLUMN")),
        ("SELECT name AS n FROM people ORDER BY n", res(["n"], [["Ada"], ["Cy"], ["Dee"], ["Eve"], ["bob"]])),
        ("SELECT name AS n FROM people WHERE n = 'Ada'", err("UNKNOWN_COLUMN")),
    ]),
    fixture("parse", "syntax", [
        ("SELECT FROM people", err("PARSE_ERROR")),
        ("SELECT name FROM people WHERE", err("PARSE_ERROR")),
        ("select name from people order by name desc limit 1", res(["name"], [["bob"]])),
        ("SELECT 'it''s', 1.5 FROM people WHERE id = 1", res(cols(2), [["it's", 1.5]])),
        ("SELECT name FROM people extra words", err("PARSE_ERROR")),
        ("SELECT FOO(name) FROM people", err("PARSE_ERROR")),
        ("SELECT AVG(DISTINCT age) FROM people", err("PARSE_ERROR")),
        ("SELECT nme FROM people ORDER BY 2", err("PARSE_ERROR")),
        ("SELECT name FROM people;", err("PARSE_ERROR")),
    ]),
    fixture("error-order", "which-error-first", [
        ("SELECT nme, COUNT(*) FROM people GROUP BY city", err("UNKNOWN_COLUMN")),
        ("SELECT name, 1 / 0 FROM people GROUP BY city", err("GROUPING_ERROR")),
        ("SELECT 1 / 0, 'a' + 1 FROM people WHERE id = 1", err("DIVISION_BY_ZERO")),
        ("SELECT name FROM people WHERE age / 0 > 1 AND id = 99", err("DIVISION_BY_ZERO")),
        ("SELECT name FROM people WHERE id = 99 AND age / 0 > 1", res(["name"], [])),
        ("SELECT 1 / 0 FROM people WHERE id > 99", res(cols(1), [])),
        ("SELECT name FROM people WHERE name = 'Ada' ORDER BY 'x' + 1", err("TYPE_MISMATCH")),
    ]),
]
