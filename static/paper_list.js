'use strict';

const UTag = props => {
    const tag_name = props.tag;
    const turl = "/?rank=tags&tags=" + tag_name;
    return (
        <div class='rel_utag'>
            <a href={turl}>
                {tag_name}
            </a>
        </div>
    )
}

const Paper = props => {
    const p = props.paper;

    const adder = () => fetch("/add/" + p.id + "/" + prompt("tag to add to this paper:"))
                        .then(response => console.log(response.text()));
    const subber = () => fetch("/sub/" + p.id + "/" + prompt("tag to subtract from this paper:"))
                        .then(response => console.log(response.text()));
    const utags = p.utags.map((utxt, ix) => <UTag key={ix} tag={utxt} />);
    const similar_url = "/?rank=pid&pid=" + p.id;
    const inspect_url = "/inspect?pid=" + p.id;
    const thumb_img = p.thumb_url === '' ? null : <div class='rel_img'><img src={p.thumb_url} /></div>;
    // if the user is logged in then we can show add/sub buttons
    let utag_controls = null;
    if(user) {
        utag_controls = (
            <div class='rel_utags'>
                <div class="rel_utag rel_utag_add" onClick={adder}>+</div>
                <div class="rel_utag rel_utag_sub" onClick={subber}>-</div>
                {utags}
            </div>
        )
    }

    return (
    <div class='rel_paper'>
        <div class="rel_score">{p.weight.toFixed(2)}</div>
        <div class='rel_title'><a href={'http://arxiv.org/abs/' + p.id}>{p.title}</a></div>
        <div class='rel_authors'>{p.authors}</div>
        <div class="rel_time">{p.time}</div>
        <div class='rel_tags'>{p.tags}</div>
        {utag_controls}
        {thumb_img}
        <div class='rel_abs'>{p.summary}</div>
        <div class='rel_more'><a href={similar_url}>similar</a></div>
        <div class='rel_inspect'><a href={inspect_url}>inspect</a></div>
    </div>
    )
}

const PaperList = props => {
    const lst = props.papers;
    const plst = lst.map((jpaper, ix) => <Paper key={ix} paper={jpaper} />);
    return (
        <div>
            <div id="paperList" class="rel_papers">
                {plst}
            </div>
        </div>
    )
}

const Tag = props => {
    const t = props.tag;
    const turl = "/?rank=tags&tags=" + t.name;
    const tag_class = 'rel_utag' + (t.name === 'all' ? ' rel_utag_all' : '');
    return (
        <div class={tag_class}>
            <a href={turl}>
                {t.n} {t.name}
            </a>
        </div>
    )
}

const TagList = props => {
    const lst = props.tags;
    const tlst = lst.map((jtag, ix) => <Tag key={ix} tag={jtag} />);
    const deleter = () => fetch("/del/" + prompt("delete tag name:"))
                          .then(response => console.log(response.text()));
    // show the #wordwrap element if the user clicks inspect
    const show_inspect = () => { document.getElementById("wordwrap").style.display = "block"; };
    const inspect_elt = words.length > 0 ? <div id="inspect_svm" onClick={show_inspect}>inspect</div> : null;
    return (
        <div>
            <div class="rel_tag" onClick={deleter}>-</div>
            <div id="tagList" class="rel_utags">
                {tlst}
            </div>
            {inspect_elt}
        </div>
    )
}

// render papers into #wrap
ReactDOM.render(<PaperList papers={papers} />, document.getElementById('wrap'));

// render tags into #tagwrap, if it exists
let tagwrap_elt = document.getElementById('tagwrap');
if (tagwrap_elt) {
    ReactDOM.render(<TagList tags={tags} />, tagwrap_elt);
}
