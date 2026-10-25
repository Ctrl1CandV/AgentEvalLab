const C = window.CONTENT;
const $ = selector => document.querySelector(selector);
let sorted = false;
$("#brand").textContent = C.brand;
$("#title").textContent = C.title;
$("#sort").textContent = C.sortLabel;
$("#genre").append(new Option(C.allGenres, ""), ...C.genres.map(genre => new Option(genre, genre)));
const genreClass = genre => `genre-${genre.toLowerCase()}`;
function render() {
  const query = $("#search").value.trim().toLowerCase();
  const genre = $("#genre").value;
  let books = C.books.filter(book => book.title.toLowerCase().includes(query) && (!genre || book.genre === genre));
  if (sorted) books = [...books].sort((left, right) => left.year - right.year);
  $('[data-role="books-table"] tbody').replaceChildren(...books.map(book => {
    const row = document.createElement("tr");
    row.innerHTML = '<th scope="row"></th><td></td><td><span class="tag"></span></td><td class="num"></td>';
    row.children[0].textContent = book.title;
    row.children[1].textContent = book.author;
    row.querySelector(".tag").textContent = book.genre;
    row.querySelector(".tag").classList.add(genreClass(book.genre));
    row.children[3].textContent = book.year;
    return row;
  }));
  $('[data-role="results-count"]').textContent = C.countFormat.replace("{n}", books.length);
  $("#empty").hidden = books.length > 0;
  $("#sort").setAttribute("aria-pressed", String(sorted));
  $("#year-head").setAttribute("aria-sort", sorted ? "ascending" : "none");
}
$("#search").addEventListener("input", render);
$("#genre").addEventListener("change", render);
$("#sort").addEventListener("click", () => { sorted = !sorted; render(); });
render();
