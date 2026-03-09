"""Unit tests for the empty-result computation heuristic."""

from scout.actions import _seems_like_computation


class TestSeemsLikeComputation:
    """Tests for the 'surprising emptiness' heuristic."""

    # --- Should detect: non-trivial computation patterns ---

    def test_queryselector(self):
        assert _seems_like_computation("document.querySelector('.btn')") is True

    def test_queryselectorall(self):
        assert _seems_like_computation("document.querySelectorAll('p')") is True

    def test_getelementbyid(self):
        assert _seems_like_computation("document.getElementById('main')") is True

    def test_getelementsbyclassname(self):
        assert _seems_like_computation("document.getElementsByClassName('item')") is True

    def test_textcontent(self):
        assert _seems_like_computation("el.textContent") is True

    def test_innerhtml(self):
        assert _seems_like_computation("el.innerHTML") is True

    def test_value_property(self):
        assert _seems_like_computation("input.value") is True

    def test_href_property(self):
        assert _seems_like_computation("a.href") is True

    def test_src_property(self):
        assert _seems_like_computation("img.src") is True

    def test_map(self):
        assert _seems_like_computation("items.map(x => x.name)") is True

    def test_filter(self):
        assert _seems_like_computation("items.filter(x => x.active)") is True

    def test_find(self):
        assert _seems_like_computation("items.find(x => x.id === 5)") is True

    def test_reduce(self):
        assert _seems_like_computation("items.reduce((a, b) => a + b, 0)") is True

    def test_array_index_access(self):
        assert _seems_like_computation("rows[0]") is True

    def test_array_variable_index(self):
        assert _seems_like_computation("elements[i]") is True

    def test_let_assignment(self):
        assert _seems_like_computation("let result = 42") is True

    def test_const_assignment(self):
        assert _seems_like_computation("const data = getData()") is True

    def test_var_assignment(self):
        assert _seems_like_computation("var x = 1") is True

    def test_json_stringify(self):
        assert _seems_like_computation("JSON.stringify(data)") is True

    def test_json_parse(self):
        assert _seems_like_computation("JSON.parse(text)") is True

    def test_fetch(self):
        assert _seems_like_computation("fetch('/api/data')") is True

    def test_dot_json(self):
        assert _seems_like_computation("response.json()") is True

    def test_await(self):
        assert _seems_like_computation("await fetchData()") is True

    # --- Should NOT detect: side-effect-only scripts ---

    def test_bare_arithmetic(self):
        assert _seems_like_computation("2 + 2") is False

    def test_console_log(self):
        assert _seems_like_computation("console.log('hello')") is False

    def test_empty_string(self):
        assert _seems_like_computation("") is False

    def test_string_literal(self):
        assert _seems_like_computation("'hello world'") is False

    # --- The benchmark Run 2 pattern (the script that started this) ---

    def test_for_of_loop_with_queryselectorall(self):
        """The exact pattern from benchmark Run 2 that returned undefined."""
        script = """
        const paragraphs = document.querySelectorAll('#mw-content-text .mw-parser-output > p');
        let firstParagraph = '';
        for (const p of paragraphs) {
            const text = p.textContent.trim();
            if (text.length > 50) {
                firstParagraph = text;
                break;
            }
        }
        """
        assert _seems_like_computation(script) is True
