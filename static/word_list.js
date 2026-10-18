'use strict';

const Word = props => {
    const p = props.word;
    // word, weight, idf
    return (
    <div class='rel_word'>
        <div class='rel_word_weight'>{p.weight.toFixed(2)}</div>
        {/* <div class='rel_word_idf'>{p.idf.toFixed(2)}</div> */}
        <div class="rel_word_txt">{p.word}</div>
    </div>
    )
}

const WordList = props => {
    const lst = props.words;
    const words_desc = props.words_desc;
    const wlst = lst.map((jword, ix) => <Word key={ix} word={jword} />);
    return (
        <div>
            <div>{words_desc}</div>
            <div id="wordList" class="rel_words">
                {wlst}
            </div>
        </div>
    )
}

var elt = document.getElementById('wordwrap');
if(elt) {
    ReactDOM.render(<WordList words={words} words_desc={words_desc} />, elt);
}
